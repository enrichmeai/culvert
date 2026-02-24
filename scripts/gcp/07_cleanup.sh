#!/bin/bash
# =============================================================================
# Cleanup: Delete Infrastructure (Keep Project)
# =============================================================================
# Usage: ./scripts/gcp/07_cleanup.sh [generic|generic|all]
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
DEPLOYMENT="${1:-}"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    exit 1
fi

if [ -z "$DEPLOYMENT" ]; then
    echo "Usage: $0 [generic|generic|all]"
    exit 1
fi

echo -e "${RED}=============================================="
echo "⚠️  CLEANUP: Delete Infrastructure"
echo "==============================================${NC}"
echo "Project: $PROJECT_ID"
echo "Deployment: $DEPLOYMENT"
echo ""
echo -e "${YELLOW}This will delete buckets, datasets, and topics.${NC}"
echo ""
read -p "Type 'DELETE' to confirm: " -r
echo ""

if [[ ! $REPLY == "DELETE" ]]; then
    echo "Cancelled."
    exit 0
fi

# Helper functions
delete_bucket() {
    local name="$1"
    local full="gs://${PROJECT_ID}-${name}"
    if gsutil ls "$full" &>/dev/null; then
        echo -n "  Deleting: $full... "
        gsutil -m rm -r "$full" 2>/dev/null && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⚠️${NC}"
    fi
}

delete_dataset() {
    local name="$1"
    if bq show --project_id="$PROJECT_ID" "$name" &>/dev/null; then
        echo -n "  Deleting: $name... "
        bq rm -r -f --project_id="$PROJECT_ID" "$name" && echo -e "${GREEN}✅${NC}"
    fi
}

delete_subscription() {
    local name="$1"
    if gcloud pubsub subscriptions describe "$name" --project="$PROJECT_ID" &>/dev/null; then
        echo -n "  Deleting: $name... "
        gcloud pubsub subscriptions delete "$name" --project="$PROJECT_ID" --quiet && echo -e "${GREEN}✅${NC}"
    fi
}

delete_topic() {
    local name="$1"
    if gcloud pubsub topics describe "$name" --project="$PROJECT_ID" &>/dev/null; then
        echo -n "  Deleting: $name... "
        gcloud pubsub topics delete "$name" --project="$PROJECT_ID" --quiet && echo -e "${GREEN}✅${NC}"
    fi
}

cleanup_em() {
    echo -e "${BLUE}=== Deleting Generic Infrastructure ===${NC}"
    echo ""
    echo "Subscriptions:"
    delete_subscription "generic-file-notifications-sub"
    delete_subscription "generic-pipeline-events-sub"
    echo "Topics:"
    delete_topic "generic-file-notifications"
    delete_topic "generic-pipeline-events"
    echo "Datasets:"
    delete_dataset "odp_generic"
    delete_dataset "fdp_generic"
    echo "Buckets:"
    delete_bucket "generic-landing"
    delete_bucket "generic-archive"
    delete_bucket "generic-error"
    delete_bucket "generic-temp"
    echo ""
}

cleanup_loa() {
    echo -e "${BLUE}=== Deleting Generic Infrastructure ===${NC}"
    echo ""
    echo "Subscriptions:"
    delete_subscription "generic-file-notifications-sub"
    delete_subscription "generic-pipeline-events-sub"
    echo "Topics:"
    delete_topic "generic-file-notifications"
    delete_topic "generic-pipeline-events"
    echo "Datasets:"
    delete_dataset "odp_generic"
    delete_dataset "fdp_generic"
    echo "Buckets:"
    delete_bucket "generic-landing"
    delete_bucket "generic-archive"
    delete_bucket "generic-error"
    delete_bucket "generic-temp"
    echo ""
}

cleanup_shared() {
    echo -e "${BLUE}=== Deleting Shared Infrastructure ===${NC}"
    echo ""
    echo "Datasets:"
    delete_dataset "job_control"
    echo ""
}

case "$DEPLOYMENT" in
    generic)  cleanup_em ;;
    generic) cleanup_loa ;;
    all) cleanup_em; cleanup_loa; cleanup_shared ;;
    *)   echo "Usage: $0 [generic|generic|all]"; exit 1 ;;
esac

echo -e "${GREEN}✅ Cleanup complete!${NC}"

