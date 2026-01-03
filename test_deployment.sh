#!/bin/bash
# test_deployment.sh - Test deployed pipeline by pushing a file to GCS
#
# Usage:
#   ./test_deployment.sh em     # Test EM deployment
#   ./test_deployment.sh loa    # Test LOA deployment
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - GCP project deployed with terraform
#   - Environment variables set (or will prompt)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values (override with environment variables)
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"

print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check gcloud
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    print_success "gcloud CLI found"

    # Check gsutil
    if ! command -v gsutil &> /dev/null; then
        print_error "gsutil not found. Install Google Cloud SDK"
        exit 1
    fi
    print_success "gsutil found"

    # Check project ID
    if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
        if [ -z "$PROJECT_ID" ]; then
            print_error "No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
            exit 1
        fi
    fi
    print_success "Project ID: $PROJECT_ID"

    # Check authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        print_error "Not authenticated. Run: gcloud auth login"
        exit 1
    fi
    print_success "Authenticated with GCP"
}

# Generate test data file with HDR/TRL
generate_em_test_file() {
    local entity=$1
    local date=$(date +%Y%m%d)
    local output_file="/tmp/em_${entity}_test_${date}.csv"

    case $entity in
        customers)
            cat > "$output_file" << EOF
HDR|EM|Customers|${date}
customer_id,name,ssn,account_status,created_date
CUST001,John Doe,123-45-6789,ACTIVE,2026-01-01
CUST002,Jane Smith,987-65-4321,ACTIVE,2026-01-01
CUST003,Bob Johnson,456-78-9012,INACTIVE,2026-01-01
TRL|RecordCount=3|Checksum=abc123
EOF
            ;;
        accounts)
            cat > "$output_file" << EOF
HDR|EM|Accounts|${date}
account_id,customer_id,account_type,balance,opened_date
ACC001,CUST001,CHECKING,5000.00,2026-01-01
ACC002,CUST001,SAVINGS,15000.00,2026-01-01
ACC003,CUST002,CHECKING,7500.00,2026-01-01
TRL|RecordCount=3|Checksum=def456
EOF
            ;;
        decision)
            cat > "$output_file" << EOF
HDR|EM|Decision|${date}
decision_id,customer_id,decision_type,score,decision_date
DEC001,CUST001,CREDIT,750,2026-01-01
DEC002,CUST002,CREDIT,680,2026-01-01
DEC003,CUST003,CREDIT,720,2026-01-01
TRL|RecordCount=3|Checksum=ghi789
EOF
            ;;
    esac

    echo "$output_file"
}

generate_loa_test_file() {
    local date=$(date +%Y%m%d)
    local output_file="/tmp/loa_applications_test_${date}.csv"

    cat > "$output_file" << EOF
HDR|LOA|Applications|${date}
application_id,customer_id,ssn,loan_amount,interest_rate,term_months,application_date,application_status,branch_code,product_type
APP001,CUST001,123-45-6789,50000.00,5.5,60,2026-01-01,PENDING,BR001,AUTO
APP002,CUST002,987-65-4321,75000.00,4.9,48,2026-01-01,APPROVED,BR002,HOME
APP003,CUST003,456-78-9012,25000.00,6.2,36,2026-01-01,PENDING,BR001,PERSONAL
TRL|RecordCount=3|Checksum=xyz789
EOF

    echo "$output_file"
}

# Upload file to GCS and create .ok trigger
upload_and_trigger() {
    local system=$1
    local data_file=$2
    local bucket="${PROJECT_ID}-${system}-staging-landing"
    local filename=$(basename "$data_file")
    local gcs_path="gs://${bucket}/${system}/${filename}"

    print_header "Uploading Test File"

    # Check if bucket exists
    if ! gsutil ls "gs://${bucket}" &> /dev/null; then
        print_error "Bucket not found: gs://${bucket}"
        print_info "Make sure terraform has been applied for ${system}"
        exit 1
    fi
    print_success "Bucket exists: gs://${bucket}"

    # Upload data file
    print_info "Uploading: ${data_file} → ${gcs_path}"
    gsutil cp "$data_file" "$gcs_path"
    print_success "Data file uploaded"

    # Create and upload .ok trigger file
    local ok_file="${data_file}.ok"
    touch "$ok_file"
    print_info "Creating trigger: ${gcs_path}.ok"
    gsutil cp "$ok_file" "${gcs_path}.ok"
    print_success ".ok trigger file uploaded"

    # Cleanup local files
    rm -f "$data_file" "$ok_file"

    echo "$gcs_path"
}

# Check Pub/Sub for message
check_pubsub() {
    local system=$1
    local subscription="${system}-file-notifications-sub"

    print_header "Checking Pub/Sub Subscription"

    print_info "Subscription: $subscription"
    print_info "Waiting for message (10 seconds)..."

    # Pull message (peek only, don't ack)
    local message=$(gcloud pubsub subscriptions pull "$subscription" \
        --project="$PROJECT_ID" \
        --limit=1 \
        --format="json" \
        --auto-ack=false 2>/dev/null || echo "")

    if [ -n "$message" ] && [ "$message" != "[]" ]; then
        print_success "Message found in Pub/Sub!"
        echo "$message" | python3 -m json.tool 2>/dev/null || echo "$message"
    else
        print_info "No message yet (pipeline may have already processed it)"
    fi
}

# Check BigQuery for data
check_bigquery() {
    local system=$1
    local table=$2

    print_header "Checking BigQuery"

    local dataset="odp_${system}"
    local full_table="${PROJECT_ID}.${dataset}.${table}"

    print_info "Querying: ${full_table}"

    local query="SELECT COUNT(*) as row_count, MAX(_processed_ts) as last_processed FROM \`${full_table}\` WHERE DATE(_extract_date) = CURRENT_DATE()"

    local result=$(bq query --use_legacy_sql=false --format=json "$query" 2>/dev/null || echo "[]")

    if [ "$result" != "[]" ]; then
        print_success "Data found in BigQuery!"
        echo "$result" | python3 -m json.tool 2>/dev/null || echo "$result"
    else
        print_info "No data found yet (pipeline may still be processing)"
    fi
}

# Check file archive
check_archive() {
    local system=$1
    local original_path=$2

    print_header "Checking Archive"

    local archive_bucket="${PROJECT_ID}-${system}-staging-archive"
    local filename=$(basename "$original_path")

    print_info "Checking archive bucket: gs://${archive_bucket}"

    local archived=$(gsutil ls "gs://${archive_bucket}/**/${filename}" 2>/dev/null || echo "")

    if [ -n "$archived" ]; then
        print_success "File archived!"
        echo "$archived"
    else
        print_info "File not archived yet (pipeline may still be processing)"
    fi
}

# Monitor Airflow DAG (if Cloud Composer)
check_airflow() {
    local system=$1

    print_header "Checking Airflow DAG Status"

    print_info "To check Airflow status:"
    echo "  1. Go to Cloud Composer in GCP Console"
    echo "  2. Click on your environment"
    echo "  3. Open Airflow UI"
    echo "  4. Find DAG: ${system}_daily_pipeline"
    echo "  5. Check latest run status"
}

# Main test flow for EM
test_em() {
    print_header "Testing EM Deployment"

    check_prerequisites

    # Generate and upload all 3 entity files
    for entity in customers accounts decision; do
        print_info "Generating ${entity} test file..."
        local file=$(generate_em_test_file "$entity")
        local gcs_path=$(upload_and_trigger "em" "$file")

        sleep 2  # Brief pause between uploads
    done

    print_header "Waiting for Pipeline (30 seconds)"
    print_info "The pipeline needs time to:"
    echo "  1. Receive Pub/Sub notification"
    echo "  2. Validate files"
    echo "  3. Load to BigQuery"
    echo "  4. Archive files"
    sleep 30

    # Check results
    check_pubsub "em"
    check_bigquery "em" "customers"
    check_bigquery "em" "accounts"
    check_bigquery "em" "decision"
    check_archive "em" "$gcs_path"
    check_airflow "em"

    print_header "EM Deployment Test Complete"
    echo ""
    echo "Next steps:"
    echo "  1. Check Airflow UI for DAG run status"
    echo "  2. Query BigQuery tables for loaded data"
    echo "  3. Check archive bucket for processed files"
}

# Main test flow for LOA
test_loa() {
    print_header "Testing LOA Deployment"

    check_prerequisites

    # Generate and upload test file
    print_info "Generating applications test file..."
    local file=$(generate_loa_test_file)
    local gcs_path=$(upload_and_trigger "loa" "$file")

    print_header "Waiting for Pipeline (30 seconds)"
    print_info "The pipeline needs time to:"
    echo "  1. Receive Pub/Sub notification"
    echo "  2. Validate file"
    echo "  3. Load to BigQuery ODP"
    echo "  4. Transform to FDP tables"
    echo "  5. Archive file"
    sleep 30

    # Check results
    check_pubsub "loa"
    check_bigquery "loa" "applications"
    check_archive "loa" "$gcs_path"
    check_airflow "loa"

    print_header "LOA Deployment Test Complete"
    echo ""
    echo "Next steps:"
    echo "  1. Check Airflow UI for DAG run status"
    echo "  2. Query BigQuery ODP table: odp_loa.applications"
    echo "  3. Query BigQuery FDP tables:"
    echo "     - fdp_loa.event_transaction_excess"
    echo "     - fdp_loa.portfolio_account_excess"
    echo "  4. Check archive bucket for processed files"
}

# Show usage
show_usage() {
    echo "Usage: $0 <system>"
    echo ""
    echo "Systems:"
    echo "  em   - Test EM (Application A) deployment"
    echo "  loa  - Test LOA (Application B Application) deployment"
    echo ""
    echo "Environment Variables:"
    echo "  GCP_PROJECT_ID  - GCP project ID (or uses gcloud default)"
    echo "  GCP_REGION      - GCP region (default: us-central1)"
    echo ""
    echo "Examples:"
    echo "  $0 em"
    echo "  GCP_PROJECT_ID=my-project $0 loa"
}

# Main
case "${1:-}" in
    em)
        test_em
        ;;
    loa)
        test_loa
        ;;
    -h|--help)
        show_usage
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

