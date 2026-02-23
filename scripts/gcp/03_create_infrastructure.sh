#!/bin/bash
# =============================================================================
# Step 3: Create Infrastructure (Buckets, Datasets, Topics)
# =============================================================================
# Usage: ./scripts/gcp/03_create_infrastructure.sh [application1|application2|all]
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

# Application1 Infrastructure
setup_em() {
    echo -e "${BLUE}=== Application1 Infrastructure ===${NC}"
    echo ""
    echo "GCS Buckets:"
    create_bucket "application1-landing"
    create_bucket "application1-archive"
    create_bucket "application1-error"
    create_bucket "application1-temp"

    echo ""
    echo "BigQuery Datasets:"
    create_dataset "odp_application1"
    create_dataset "fdp_application1"
    create_dataset "job_control"

    echo ""
    echo "Pub/Sub:"
    create_topic "application1-file-notifications"
    create_topic "application1-pipeline-events"
    create_subscription "application1-file-notifications-sub" "application1-file-notifications"
    create_subscription "application1-pipeline-events-sub" "application1-pipeline-events"
    echo ""
}

# Application2 Infrastructure
setup_loa() {
    echo -e "${BLUE}=== Application2 Infrastructure ===${NC}"
    echo ""
    echo "GCS Buckets:"
    create_bucket "application2-landing"
    create_bucket "application2-archive"
    create_bucket "application2-error"
    create_bucket "application2-temp"

    echo ""
    echo "BigQuery Datasets:"
    create_dataset "odp_application2"
    create_dataset "fdp_application2"

    echo ""
    echo "Pub/Sub:"
    create_topic "application2-file-notifications"
    create_topic "application2-pipeline-events"
    create_subscription "application2-file-notifications-sub" "application2-file-notifications"
    create_subscription "application2-pipeline-events-sub" "application2-pipeline-events"
    echo ""
}

# Main
case "$DEPLOYMENT" in
    application1)  setup_em ;;
    application2) setup_loa ;;
    all) setup_em; setup_loa ;;
    *)   echo "Usage: $0 [application1|application2|all]"; exit 1 ;;
esac

echo -e "${GREEN}✅ Step 3 Complete!${NC}"
echo ""
echo "Next: ./scripts/gcp/04_setup_github_actions.sh"

