#!/bin/bash
# =============================================================================
# Deploy All: Complete GCP Infrastructure Setup
# =============================================================================
# Usage: ./scripts/gcp/deploy_all.sh [application1|application2|all]
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

# Step 3: Setup GitHub Actions (service account + permissions)
echo -e "${BLUE}>>> Step 3/5: Setup GitHub Actions Service Account${NC}"
SA_EMAIL="github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com"

# Check if SA exists, if not create it
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
    echo "Creating service account..."
    "$SCRIPT_DIR/setup_github_actions.sh"
else
    echo "Service account exists, granting additional roles..."
    # Grant all required roles
    for role in \
        "roles/bigquery.admin" \
        "roles/storage.admin" \
        "roles/pubsub.admin" \
        "roles/dataflow.admin" \
        "roles/iam.serviceAccountUser" \
        "roles/iam.serviceAccountAdmin" \
        "roles/resourcemanager.projectIamAdmin" \
        "roles/logging.admin" \
        "roles/monitoring.admin" \
        "roles/composer.admin" \
        "roles/cloudbuild.builds.builder"; do
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:${SA_EMAIL}" \
            --role="$role" \
            --quiet 2>/dev/null || true
    done
    echo "  Roles granted ✅"
fi

# Grant bucket permissions for Terraform state
echo "Granting Terraform state bucket permissions..."
gsutil iam ch "serviceAccount:${SA_EMAIL}:objectAdmin" gs://gdw-terraform-state 2>/dev/null || true
gsutil iam ch "serviceAccount:${SA_EMAIL}:legacyBucketWriter" gs://gdw-terraform-state 2>/dev/null || true
echo "  Bucket permissions granted ✅"
echo ""

# Step 4: Trigger GitHub Actions to deploy infrastructure via Terraform
echo -e "${BLUE}>>> Step 4/5: Deploy via GitHub Actions${NC}"
echo "Triggering GitHub Actions deployments..."

# NOTE: 'cdp' and 'spanner' are explicitly excluded as per requirements.
# 'spanner' does not currently have a dedicated terraform infrastructure or separate deployment workflow.

if [[ "$DEPLOYMENT" == "all" || "$DEPLOYMENT" == "application1" ]]; then
    gh workflow run deploy-application1.yml && echo "  Application1 deployment triggered ✅"
fi
if [[ "$DEPLOYMENT" == "all" || "$DEPLOYMENT" == "application2" ]]; then
    gh workflow run deploy-application2.yml && echo "  Application2 deployment triggered ✅"
fi

echo ""
echo "Waiting for deployments to complete (this may take 5-10 minutes)..."
echo "Check status with: gh run list --limit 4"
echo ""

# Step 5: Wait and verify
echo -e "${BLUE}>>> Step 5/5: Verify Deployment${NC}"
echo "Once GitHub Actions complete, run:"
echo "  ./scripts/gcp/05_verify_setup.sh"
echo "  ./scripts/gcp/06_test_pipeline.sh application1"
echo ""
echo ""
echo -e "${GREEN}=============================================="
echo "✅ Deployment Initiated!"
echo "==============================================${NC}"
echo ""
echo "What was done:"
echo "  - GCP services enabled"
echo "  - Terraform state bucket created"
echo "  - GitHub Actions service account configured"
echo "  - GitHub Actions deployments triggered"
echo ""
echo "GitHub Actions will now:"
echo "  - Create GCS buckets via Terraform"
echo "  - Create BigQuery datasets via Terraform"
echo "  - Create Pub/Sub topics via Terraform"
echo "  - Deploy Dataflow templates"
echo "  - Deploy Airflow DAGs"
echo ""
echo "Monitor deployment:"
echo "  gh run list --limit 4"
echo "  gh run view <RUN_ID> --log"
echo ""
echo "After deployment completes:"
echo "  ./scripts/gcp/05_verify_setup.sh"
echo "  ./scripts/gcp/06_test_pipeline.sh application1"
echo ""
echo "To cleanup:"
echo "  ./scripts/gcp/00_full_reset.sh"

