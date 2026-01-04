#!/bin/bash
# =============================================================================
# Step 3: Create Infrastructure (Buckets, Datasets, Topics)
# =============================================================================
# Usage: ./scripts/gcp/03_create_infrastructure.sh [em|loa|all]
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"
DEPLOYMENT="${1:-all}"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    exit 1
fi

echo "=============================================="
echo "Step 3: Create Infrastructure"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Deployment: $DEPLOYMENT"
echo "=============================================="
echo ""

# Helper functions
create_bucket() {
    local name="$1"
    local full="gs://${PROJECT_ID}-${name}"
    if gsutil ls "$full" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} $full"
    else
        echo -n "  Creating: $full... "
        gsutil mb -l "$REGION" -p "$PROJECT_ID" "$full" && echo -e "${GREEN}✅${NC}"
    fi
}

create_dataset() {
    local name="$1"
    if bq show --project_id="$PROJECT_ID" "$name" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} $name"
    else
        echo -n "  Creating: $name... "
        bq mk --project_id="$PROJECT_ID" --location="$REGION" "$name" && echo -e "${GREEN}✅${NC}"
    fi
}

create_topic() {
    local name="$1"
    if gcloud pubsub topics describe "$name" --project="$PROJECT_ID" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} $name"
    else
        echo -n "  Creating topic: $name... "
        gcloud pubsub topics create "$name" --project="$PROJECT_ID" && echo -e "${GREEN}✅${NC}"
    fi
}

create_subscription() {
    local name="$1"
    local topic="$2"
    if gcloud pubsub subscriptions describe "$name" --project="$PROJECT_ID" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} $name"
    else
        echo -n "  Creating subscription: $name... "
        gcloud pubsub subscriptions create "$name" --topic="$topic" --project="$PROJECT_ID" && echo -e "${GREEN}✅${NC}"
    fi
}

# EM Infrastructure
setup_em() {
    echo -e "${BLUE}=== EM Infrastructure ===${NC}"
    echo ""
    echo "GCS Buckets:"
    create_bucket "em-landing"
    create_bucket "em-archive"
    create_bucket "em-error"
    create_bucket "em-temp"

    echo ""
    echo "BigQuery Datasets:"
    create_dataset "odp_em"
    create_dataset "fdp_em"
    create_dataset "job_control"

    echo ""
    echo "Pub/Sub:"
    create_topic "em-file-notifications"
    create_topic "em-pipeline-events"
    create_subscription "em-file-notifications-sub" "em-file-notifications"
    create_subscription "em-pipeline-events-sub" "em-pipeline-events"
    echo ""
}

# LOA Infrastructure
setup_loa() {
    echo -e "${BLUE}=== LOA Infrastructure ===${NC}"
    echo ""
    echo "GCS Buckets:"
    create_bucket "loa-landing"
    create_bucket "loa-archive"
    create_bucket "loa-error"
    create_bucket "loa-temp"

    echo ""
    echo "BigQuery Datasets:"
    create_dataset "odp_loa"
    create_dataset "fdp_loa"

    echo ""
    echo "Pub/Sub:"
    create_topic "loa-file-notifications"
    create_topic "loa-pipeline-events"
    create_subscription "loa-file-notifications-sub" "loa-file-notifications"
    create_subscription "loa-pipeline-events-sub" "loa-pipeline-events"
    echo ""
}

# Main
case "$DEPLOYMENT" in
    em)  setup_em ;;
    loa) setup_loa ;;
    all) setup_em; setup_loa ;;
    *)   echo "Usage: $0 [em|loa|all]"; exit 1 ;;
esac

echo -e "${GREEN}✅ Step 3 Complete!${NC}"
echo ""
echo "Next: ./scripts/gcp/04_setup_github_actions.sh"

