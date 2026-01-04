#!/bin/bash
# =============================================================================
# Step 1: Enable Required GCP Services
# =============================================================================
# Usage: ./scripts/gcp/01_enable_services.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    echo "Run: gcloud config set project <PROJECT_ID>"
    exit 1
fi

echo "=============================================="
echo "Step 1: Enable Required GCP Services"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "=============================================="
echo ""

SERVICES=(
    "bigquery.googleapis.com"
    "storage.googleapis.com"
    "pubsub.googleapis.com"
    "dataflow.googleapis.com"
    "cloudkms.googleapis.com"
    "monitoring.googleapis.com"
    "logging.googleapis.com"
)

echo "Enabling services..."
for service in "${SERVICES[@]}"; do
    echo -n "  $service... "
    gcloud services enable "$service" --project="$PROJECT_ID" 2>/dev/null && \
        echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}(already enabled)${NC}"
done

echo ""
echo -e "${GREEN}✅ Step 1 Complete!${NC}"
echo ""
echo "Next: ./scripts/gcp/02_create_state_bucket.sh"

