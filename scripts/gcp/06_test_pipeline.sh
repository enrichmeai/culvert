#!/bin/bash
# =============================================================================
# Step 6: Test Pipeline with Sample Data
# =============================================================================
# Usage: ./scripts/gcp/06_test_pipeline.sh [em|loa]
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
DEPLOYMENT="${1:-em}"
DATE=$(date +%Y%m%d)

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    exit 1
fi

echo "=============================================="
echo "Step 6: Test Pipeline"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Deployment: $DEPLOYMENT"
echo "Date: $DATE"
echo "=============================================="
echo ""

# EM Test Data
test_em() {
    echo -e "${BLUE}=== Creating EM Test Data ===${NC}"
    echo ""

    # Customers
    echo "Creating em_customers_${DATE}.csv..."
    cat > /tmp/em_customers_${DATE}.csv << EOF
HDR|EM|Customers|${DATE}
customer_id,name,email,status,created_date
CUST001,John Doe,john@example.com,ACTIVE,2025-01-15
CUST002,Jane Smith,jane@example.com,ACTIVE,2025-01-14
CUST003,Bob Wilson,bob@example.com,INACTIVE,2025-01-13
TRL|RecordCount=3|Checksum=abc123
EOF

    # Accounts
    echo "Creating em_accounts_${DATE}.csv..."
    cat > /tmp/em_accounts_${DATE}.csv << EOF
HDR|EM|Accounts|${DATE}
account_id,customer_id,account_type,balance,opened_date
ACC001,CUST001,CHECKING,1500.00,2025-01-15
ACC002,CUST001,SAVINGS,5000.00,2025-01-15
ACC003,CUST002,CHECKING,2500.00,2025-01-14
TRL|RecordCount=3|Checksum=def456
EOF

    # Decision
    echo "Creating em_decision_${DATE}.csv..."
    cat > /tmp/em_decision_${DATE}.csv << EOF
HDR|EM|Decision|${DATE}
decision_id,customer_id,decision_code,score,decision_date
DEC001,CUST001,APPROVED,750,2025-01-15
DEC002,CUST002,APPROVED,680,2025-01-14
DEC003,CUST003,DECLINED,450,2025-01-13
TRL|RecordCount=3|Checksum=ghi789
EOF

    BUCKET="gs://${PROJECT_ID}-em-landing"
    TOPIC="em-file-notifications"

    echo ""
    echo -e "${BLUE}=== Uploading to $BUCKET ===${NC}"

    for entity in customers accounts decision; do
        FILE="/tmp/em_${entity}_${DATE}.csv"
        echo -n "  Uploading $(basename $FILE)... "
        gsutil cp "$FILE" "$BUCKET/" && echo -e "${GREEN}✅${NC}"

        # Create .ok trigger file
        touch "${FILE}.ok"
        echo -n "  Uploading $(basename $FILE).ok... "
        gsutil cp "${FILE}.ok" "$BUCKET/" && echo -e "${GREEN}✅${NC}"
    done

    echo ""
    echo -e "${BLUE}=== Publishing Notifications ===${NC}"

    for entity in customers accounts decision; do
        echo -n "  Publishing em_${entity}_${DATE}.csv... "
        gcloud pubsub topics publish "$TOPIC" \
            --project="$PROJECT_ID" \
            --message="{\"file\": \"em_${entity}_${DATE}.csv\", \"entity\": \"${entity}\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
            && echo -e "${GREEN}✅${NC}"
    done
}

# LOA Test Data
test_loa() {
    echo -e "${BLUE}=== Creating LOA Test Data ===${NC}"
    echo ""

    echo "Creating loa_applications_${DATE}.csv..."
    cat > /tmp/loa_applications_${DATE}.csv << EOF
HDR|LOA|Applications|${DATE}
application_id,customer_id,loan_type,amount,status,submitted_date
APP001,CUST001,PERSONAL,10000.00,PENDING,2025-01-15
APP002,CUST002,MORTGAGE,250000.00,APPROVED,2025-01-14
APP003,CUST003,AUTO,25000.00,DECLINED,2025-01-13
TRL|RecordCount=3|Checksum=loa123
EOF

    BUCKET="gs://${PROJECT_ID}-loa-landing"
    TOPIC="loa-file-notifications"
    FILE="/tmp/loa_applications_${DATE}.csv"

    echo ""
    echo -e "${BLUE}=== Uploading to $BUCKET ===${NC}"

    echo -n "  Uploading $(basename $FILE)... "
    gsutil cp "$FILE" "$BUCKET/" && echo -e "${GREEN}✅${NC}"

    touch "${FILE}.ok"
    echo -n "  Uploading $(basename $FILE).ok... "
    gsutil cp "${FILE}.ok" "$BUCKET/" && echo -e "${GREEN}✅${NC}"

    echo ""
    echo -e "${BLUE}=== Publishing Notification ===${NC}"

    echo -n "  Publishing loa_applications_${DATE}.csv... "
    gcloud pubsub topics publish "$TOPIC" \
        --project="$PROJECT_ID" \
        --message="{\"file\": \"loa_applications_${DATE}.csv\", \"entity\": \"applications\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
        && echo -e "${GREEN}✅${NC}"
}

# Main
case "$DEPLOYMENT" in
    em)  test_em ;;
    loa) test_loa ;;
    *)   echo "Usage: $0 [em|loa]"; exit 1 ;;
esac

echo ""
echo -e "${GREEN}=============================================="
echo "Test data uploaded successfully!"
echo "==============================================${NC}"
echo ""
echo "Monitor with:"
echo "  # Check files in bucket"
echo "  gsutil ls gs://${PROJECT_ID}-${DEPLOYMENT}-landing/"
echo ""
echo "  # Check Pub/Sub messages"
echo "  gcloud pubsub subscriptions pull ${DEPLOYMENT}-file-notifications-sub --auto-ack"
echo ""
echo "  # Check BigQuery (after pipeline runs)"
echo "  bq query --use_legacy_sql=false 'SELECT * FROM odp_${DEPLOYMENT}.* LIMIT 10'"
echo ""
echo "  # Check Dataflow jobs"
echo "  gcloud dataflow jobs list"

