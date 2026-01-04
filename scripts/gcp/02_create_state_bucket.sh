#!/bin/bash
# =============================================================================
# Step 2: Create Terraform State Bucket
# =============================================================================
# Usage: ./scripts/gcp/02_create_state_bucket.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"
STATE_BUCKET="gdw-terraform-state"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    exit 1
fi

echo "=============================================="
echo "Step 2: Create Terraform State Bucket"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Bucket: gs://$STATE_BUCKET"
echo "Region: $REGION"
echo "=============================================="
echo ""

# Check if bucket exists
if gsutil ls "gs://$STATE_BUCKET" &>/dev/null; then
    echo -e "${YELLOW}Bucket already exists: gs://$STATE_BUCKET${NC}"
else
    echo -n "Creating bucket... "
    gsutil mb -l "$REGION" -p "$PROJECT_ID" "gs://$STATE_BUCKET" && \
        echo -e "${GREEN}✅${NC}"
fi

# Enable versioning
echo -n "Enabling versioning... "
gsutil versioning set on "gs://$STATE_BUCKET" 2>/dev/null && \
    echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}(already enabled)${NC}"

echo ""
echo -e "${GREEN}✅ Step 2 Complete!${NC}"
echo ""
echo "Next: ./scripts/gcp/03_create_infrastructure.sh all"

