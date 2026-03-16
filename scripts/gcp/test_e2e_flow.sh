#!/bin/bash
# =============================================================================
# GCP E2E Test Script for 3-Unit Deployment Architecture
# =============================================================================
# Tests the complete flow: GCS → Pub/Sub → Dataflow → BigQuery
#
# Usage: ./scripts/gcp/test_e2e_flow.sh [generic|generic|all]
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - GCP project set
#   - Terraform infrastructure deployed
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"
SYSTEM="${1:-all}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=============================================="
echo "GCP E2E Test - 3-Unit Architecture"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "System: $SYSTEM"
echo "Timestamp: $TIMESTAMP"
echo "=============================================="

# -----------------------------------------------------------------------------
# Step 1: Check Prerequisites
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 1: Check Prerequisites${NC}"

check_resource() {
    local type=$1
    local name=$2
    local check_cmd=$3

    if eval "$check_cmd" &>/dev/null; then
        echo -e "  ✅ $type: $name"
        return 0
    else
        echo -e "  ❌ $type: $name (missing)"
        return 1
    fi
}

MISSING=0

# Check buckets
echo "Checking GCS buckets..."
check_resource "Bucket" "${PROJECT_ID}-generic-int-landing" "gsutil ls gs://${PROJECT_ID}-generic-int-landing" || MISSING=1
check_resource "Bucket" "${PROJECT_ID}-generic-int-landing" "gsutil ls gs://${PROJECT_ID}-generic-int-landing" || MISSING=1

# Check BigQuery datasets
echo "Checking BigQuery datasets..."
check_resource "Dataset" "odp_generic" "bq show ${PROJECT_ID}:odp_generic" || MISSING=1
check_resource "Dataset" "odp_generic" "bq show ${PROJECT_ID}:odp_generic" || MISSING=1
check_resource "Dataset" "fdp_generic" "bq show ${PROJECT_ID}:fdp_generic" || MISSING=1
check_resource "Dataset" "fdp_generic" "bq show ${PROJECT_ID}:fdp_generic" || MISSING=1

# Check Pub/Sub topics
echo "Checking Pub/Sub topics..."
check_resource "Topic" "generic-file-notifications" "gcloud pubsub topics describe generic-file-notifications" || MISSING=1
check_resource "Topic" "generic-file-notifications" "gcloud pubsub topics describe generic-file-notifications" || MISSING=1

if [ $MISSING -eq 1 ]; then
    echo -e "\n${YELLOW}Some resources are missing. Run infrastructure setup first:${NC}"
    echo "  ./scripts/gcp/deploy_all.sh"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# Step 2: Create Test Data Files
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 2: Create Test Data Files${NC}"

TEST_DIR="/tmp/gcp_e2e_test_${TIMESTAMP}"
mkdir -p "$TEST_DIR"

if [ "$SYSTEM" = "generic" ] || [ "$SYSTEM" = "all" ]; then
    echo "Creating Generic test files..."

    # Generic Customers file
    cat > "$TEST_DIR/generic_customers.csv" << 'EOF'
HDR|Generic|CUSTOMERS|20260106
customer_id,first_name,last_name,ssn,dob,status,created_date
C001,John,Doe,123-45-6789,1985-06-15,A,2025-01-15
C002,Jane,Smith,987-65-4321,1990-03-22,A,2025-02-20
C003,Bob,Johnson,555-55-5555,1978-11-08,I,2025-03-10
TRL|RecordCount=3|Checksum=abc123
EOF

    # Generic Accounts file
    cat > "$TEST_DIR/generic_accounts.csv" << 'EOF'
HDR|Generic|ACCOUNTS|20260106
account_id,customer_id,account_type,balance,status,open_date
A001,C001,CHECKING,1500.00,A,2025-01-20
A002,C001,SAVINGS,5000.00,A,2025-01-21
A003,C002,CHECKING,2500.00,A,2025-02-25
TRL|RecordCount=3|Checksum=def456
EOF

    # Generic Decision file
    cat > "$TEST_DIR/generic_decision.csv" << 'EOF'
HDR|Generic|DECISION|20260106
decision_id,customer_id,decision_code,decision_date,score,reason_codes
D001,C001,APPROVE,2025-01-25,750,GOOD_HISTORY
D002,C002,APPROVE,2025-02-28,680,STABLE_INCOME
D003,C003,DECLINE,2025-03-15,520,LOW_SCORE
TRL|RecordCount=3|Checksum=ghi789
EOF

    echo "  ✅ Generic test files created"
fi

if [ "$SYSTEM" = "generic" ] || [ "$SYSTEM" = "all" ]; then
    echo "Creating Generic test files..."

    # Generic Applications file
    cat > "$TEST_DIR/generic_applications.csv" << 'EOF'
HDR|Generic|APPLICATIONS|20260106
application_id,customer_id,loan_amount,interest_rate,term_months,application_date,status,event_type,account_type
APP001,C001,25000.00,5.5,60,2025-01-10,APPROVED,NEW_APPLICATION,PORTFOLIO
APP002,C002,15000.00,6.0,36,2025-02-15,PENDING,NEW_APPLICATION,EXCESS
APP003,C003,50000.00,4.5,84,2025-03-20,APPROVED,REFINANCE,PORTFOLIO
TRL|RecordCount=3|Checksum=jkl012
EOF

    echo "  ✅ Generic test files created"
fi

# -----------------------------------------------------------------------------
# Step 3: Upload Test Files to GCS
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 3: Upload Test Files to GCS${NC}"

if [ "$SYSTEM" = "generic" ] || [ "$SYSTEM" = "all" ]; then
    echo "Uploading Generic files..."

    # Upload data files first
    gsutil cp "$TEST_DIR/generic_customers.csv" "gs://${PROJECT_ID}-generic-int-landing/generic/customers/"
    gsutil cp "$TEST_DIR/generic_accounts.csv" "gs://${PROJECT_ID}-generic-int-landing/generic/accounts/"
    gsutil cp "$TEST_DIR/generic_decision.csv" "gs://${PROJECT_ID}-generic-int-landing/generic/decision/"

    # Create .ok trigger files (this triggers Pub/Sub notification)
    touch "$TEST_DIR/customers.csv.ok"
    touch "$TEST_DIR/accounts.csv.ok"
    touch "$TEST_DIR/decision.csv.ok"

    gsutil cp "$TEST_DIR/customers.csv.ok" "gs://${PROJECT_ID}-generic-int-landing/generic/customers/"
    gsutil cp "$TEST_DIR/accounts.csv.ok" "gs://${PROJECT_ID}-generic-int-landing/generic/accounts/"
    gsutil cp "$TEST_DIR/decision.csv.ok" "gs://${PROJECT_ID}-generic-int-landing/generic/decision/"

    echo "  ✅ Generic files uploaded"
fi

if [ "$SYSTEM" = "generic" ] || [ "$SYSTEM" = "all" ]; then
    echo "Uploading Generic files..."

    gsutil cp "$TEST_DIR/generic_applications.csv" "gs://${PROJECT_ID}-generic-int-landing/generic/applications/"

    touch "$TEST_DIR/applications.csv.ok"
    gsutil cp "$TEST_DIR/applications.csv.ok" "gs://${PROJECT_ID}-generic-int-landing/generic/applications/"

    echo "  ✅ Generic files uploaded"
fi

# -----------------------------------------------------------------------------
# Step 4: Verify Pub/Sub Messages
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 4: Check Pub/Sub Messages${NC}"

if [ "$SYSTEM" = "generic" ] || [ "$SYSTEM" = "all" ]; then
    echo "Checking Generic Pub/Sub subscription..."
    MSG_COUNT=$(gcloud pubsub subscriptions pull generic-file-notifications-sub --limit=10 --auto-ack 2>/dev/null | wc -l || echo "0")
    if [ "$MSG_COUNT" -gt 1 ]; then
        echo "  ✅ Generic Pub/Sub messages received"
    else
        echo "  ⚠️  No Generic Pub/Sub messages (may need GCS notification setup)"
    fi
fi

if [ "$SYSTEM" = "generic" ] || [ "$SYSTEM" = "all" ]; then
    echo "Checking Generic Pub/Sub subscription..."
    MSG_COUNT=$(gcloud pubsub subscriptions pull generic-file-notifications-sub --limit=10 --auto-ack 2>/dev/null | wc -l || echo "0")
    if [ "$MSG_COUNT" -gt 1 ]; then
        echo "  ✅ Generic Pub/Sub messages received"
    else
        echo "  ⚠️  No Generic Pub/Sub messages (may need GCS notification setup)"
    fi
fi

# -----------------------------------------------------------------------------
# Step 5: Summary
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}=============================================="
echo "E2E Test Setup Complete"
echo "==============================================${NC}"
echo ""
echo "Test files uploaded to:"
if [ "$SYSTEM" = "generic" ] || [ "$SYSTEM" = "all" ]; then
    echo "  - gs://${PROJECT_ID}-generic-int-landing/generic/customers/"
    echo "  - gs://${PROJECT_ID}-generic-int-landing/generic/accounts/"
    echo "  - gs://${PROJECT_ID}-generic-int-landing/generic/decision/"
fi
if [ "$SYSTEM" = "generic" ] || [ "$SYSTEM" = "all" ]; then
    echo "  - gs://${PROJECT_ID}-generic-int-landing/generic/applications/"
fi
echo ""
echo "Next steps:"
echo "  1. If Airflow is running: DAGs will pick up .ok files automatically"
echo "  2. For manual Dataflow test, run:"
echo "     python -m data_ingestion.pipeline.runner \\"
echo "       --source_file=gs://${PROJECT_ID}-generic-int-landing/generic/customers/generic_customers_20260106.csv \\"
echo "       --output_table=${PROJECT_ID}:odp_generic.customers \\"
echo "       --entity=customers --extract_date=20260106 --run_id=test-run-1"
echo ""
echo "  3. Check BigQuery for loaded data:"
echo "     bq query 'SELECT COUNT(*) FROM \`${PROJECT_ID}.odp_generic.customers\`'"
echo ""

# Cleanup temp files
rm -rf "$TEST_DIR"

echo -e "${GREEN}Done!${NC}"

