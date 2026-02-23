#!/bin/bash
# =============================================================================
# Step 6: Test Pipeline with Sample Data
# =============================================================================
# Usage: ./scripts/gcp/06_test_pipeline.sh [application1|application2]
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
DEPLOYMENT="${1:-application1}"
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

# Application1 Test Data
test_em() {
    echo -e "${BLUE}=== Creating Application1 Test Data ===${NC}"
    echo ""

    # Customers
    echo "Creating application1_customers_${DATE}.csv..."
    cat > /tmp/application1_customers_${DATE}.csv << EOF
HDR|Application1|Customers|${DATE}
customer_id,name,email,status,created_date
CUST001,John Doe,john@example.com,ACTIVE,2025-01-15
CUST002,Jane Smith,jane@example.com,ACTIVE,2025-01-14
CUST003,Bob Wilson,bob@example.com,INACTIVE,2025-01-13
TRL|RecordCount=3|Checksum=abc123
EOF

    # Accounts
    echo "Creating application1_accounts_${DATE}.csv..."
    cat > /tmp/application1_accounts_${DATE}.csv << EOF
HDR|Application1|Accounts|${DATE}
account_id,customer_id,account_type,balance,opened_date
ACC001,CUST001,CHECKING,1500.00,2025-01-15
ACC002,CUST001,SAVINGS,5000.00,2025-01-15
ACC003,CUST002,CHECKING,2500.00,2025-01-14
TRL|RecordCount=3|Checksum=def456
EOF

    # Decision
    echo "Creating application1_decision_${DATE}.csv..."
    cat > /tmp/application1_decision_${DATE}.csv << EOF
HDR|Application1|Decision|${DATE}
decision_id,customer_id,decision_code,score,decision_date
DEC001,CUST001,APPROVED,750,2025-01-15
DEC002,CUST002,APPROVED,680,2025-01-14
DEC003,CUST003,DECLINED,450,2025-01-13
TRL|RecordCount=3|Checksum=ghi789
EOF

    BUCKET="gs://${PROJECT_ID}-application1-landing"
    TOPIC="application1-file-notifications"

    echo ""
    echo -e "${BLUE}=== Uploading to $BUCKET ===${NC}"

    for entity in customers accounts decision; do
        FILE="/tmp/application1_${entity}_${DATE}.csv"
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
        FILE_NAME="application1_${entity}_${DATE}.csv.ok"
        BUCKET_NAME="${PROJECT_ID}-application1-landing"
        echo -n "  Publishing $FILE_NAME... "
        gcloud pubsub topics publish "$TOPIC" \
            --project="$PROJECT_ID" \
            --attribute="objectId=${FILE_NAME},bucketId=${BUCKET_NAME}" \
            --message="{\"name\": \"${FILE_NAME}\", \"bucket\": \"${BUCKET_NAME}\", \"entity\": \"${entity}\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
            && echo -e "${GREEN}✅${NC}"
    done
}

# Application2 Test Data
test_loa() {
    echo -e "${BLUE}=== Creating Application2 Test Data ===${NC}"
    echo ""

    echo "Creating application2_applications_${DATE}.csv..."
    cat > /tmp/application2_applications_${DATE}.csv << EOF
HDR|Application2|Applications|${DATE}
application_id,customer_id,loan_type,amount,status,submitted_date
APP001,CUST001,PERSONAL,10000.00,PENDING,2025-01-15
APP002,CUST002,MORTGAGE,250000.00,APPROVED,2025-01-14
APP003,CUST003,AUTO,25000.00,DECLINED,2025-01-13
TRL|RecordCount=3|Checksum=loa123
EOF

    BUCKET_NAME="${PROJECT_ID}-application2-landing"
    BUCKET="gs://${BUCKET_NAME}"
    TOPIC="application2-file-notifications"
    FILE="/tmp/application2_applications_${DATE}.csv"

    echo ""
    echo -e "${BLUE}=== Uploading to $BUCKET ===${NC}"

    echo -n "  Uploading $(basename $FILE)... "
    gsutil cp "$FILE" "$BUCKET/" && echo -e "${GREEN}✅${NC}"

    touch "${FILE}.ok"
    echo -n "  Uploading $(basename $FILE).ok... "
    gsutil cp "${FILE}.ok" "$BUCKET/" && echo -e "${GREEN}✅${NC}"

    echo ""
    echo -e "${BLUE}=== Publishing Notification ===${NC}"

    FILE_NAME="application2_applications_${DATE}.csv.ok"
    echo -n "  Publishing $FILE_NAME... "
    gcloud pubsub topics publish "$TOPIC" \
        --project="$PROJECT_ID" \
        --attribute="objectId=${FILE_NAME},bucketId=${BUCKET_NAME}" \
        --message="{\"name\": \"${FILE_NAME}\", \"bucket\": \"${BUCKET_NAME}\", \"entity\": \"applications\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
        && echo -e "${GREEN}✅${NC}"
}

# Main
case "$DEPLOYMENT" in
    application1)  test_em ;;
    application2) test_loa ;;
    *)   echo "Usage: $0 [application1|application2]"; exit 1 ;;
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

