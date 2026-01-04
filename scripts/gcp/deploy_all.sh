#!/bin/bash
# =============================================================================
# Deploy All: Complete GCP Infrastructure Setup
# =============================================================================
# Usage: ./scripts/gcp/deploy_all.sh [em|loa|all]
#
# This is the ONE script to run for complete local deployment.
# It runs all steps in order:
#   1. Enable services
#   2. Create Terraform state bucket
#   3. Create infrastructure (buckets, datasets, topics)
#   4. Setup GitHub Actions (optional)
#   5. Verify setup
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
DEPLOYMENT="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    echo "Run: gcloud config set project <PROJECT_ID>"
    exit 1
fi

echo "=============================================="
echo "Deploy All GCP Infrastructure"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Deployment: $DEPLOYMENT"
echo "=============================================="
echo ""

# Step 1: Enable Services
echo -e "${BLUE}>>> Step 1/5: Enable Services${NC}"
"$SCRIPT_DIR/01_enable_services.sh"
echo ""

# Step 2: Create Terraform State Bucket
echo -e "${BLUE}>>> Step 2/5: Create Terraform State Bucket${NC}"
"$SCRIPT_DIR/02_create_state_bucket.sh"
echo ""

# Step 3: Create Infrastructure
echo -e "${BLUE}>>> Step 3/5: Create Infrastructure${NC}"
"$SCRIPT_DIR/03_create_infrastructure.sh" "$DEPLOYMENT"
echo ""

# Step 4: Verify Setup
echo -e "${BLUE}>>> Step 4/5: Verify Setup${NC}"
"$SCRIPT_DIR/05_verify_setup.sh"
echo ""

# Step 5: Upload Test Data (optional)
echo -e "${BLUE}>>> Step 5/5: Upload Test Data${NC}"
read -p "Upload test data now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [[ "$DEPLOYMENT" == "all" || "$DEPLOYMENT" == "em" ]]; then
        "$SCRIPT_DIR/06_test_pipeline.sh" em
    fi
    if [[ "$DEPLOYMENT" == "all" || "$DEPLOYMENT" == "loa" ]]; then
        "$SCRIPT_DIR/06_test_pipeline.sh" loa
    fi
fi

echo ""
echo -e "${GREEN}=============================================="
echo "✅ Deployment Complete!"
echo "==============================================${NC}"
echo ""
echo "What was created:"
echo "  - GCP services enabled"
echo "  - Terraform state bucket"
echo "  - GCS buckets for $DEPLOYMENT"
echo "  - BigQuery datasets for $DEPLOYMENT"
echo "  - Pub/Sub topics for $DEPLOYMENT"
echo ""
echo "To test:"
echo "  ./scripts/gcp/06_test_pipeline.sh em"
echo "  ./scripts/gcp/06_test_pipeline.sh loa"
echo ""
echo "To cleanup:"
echo "  ./scripts/gcp/00_full_reset.sh"

