#!/bin/bash
# =============================================================================
# FULL RESET: Delete Everything and Start Fresh
# =============================================================================
# Usage: ./scripts/gcp/00_full_reset.sh
#
# This script:
# 1. Deletes all manually created resources
# 2. Clears Terraform state
# 3. Enables all required APIs
# 4. Ready for fresh deployment
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    echo "Run: gcloud config set project <PROJECT_ID>"
    exit 1
fi

echo -e "${RED}=============================================="
echo "⚠️  FULL RESET - Delete Everything"
echo "==============================================${NC}"
echo "Project: $PROJECT_ID"
echo ""
echo "This will delete:"
echo "  - All GCS buckets (em-*, loa-*, terraform-state)"
echo "  - All BigQuery datasets (odp_*, fdp_*, job_control)"
echo "  - All Pub/Sub topics and subscriptions"
echo "  - All service accounts (em-*, loa-*)"
echo "  - Terraform state"
echo ""
read -p "Type 'RESET' to confirm: " -r
echo ""

if [[ ! $REPLY == "RESET" ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}=== Step 1: Delete Pub/Sub Subscriptions ===${NC}"
for sub in em-file-notifications-sub em-pipeline-events-sub loa-file-notifications-sub loa-pipeline-events-sub; do
    gcloud pubsub subscriptions delete "$sub" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $sub" || true
done

echo ""
echo -e "${BLUE}=== Step 2: Delete Pub/Sub Topics ===${NC}"
for topic in em-file-notifications em-pipeline-events loa-file-notifications loa-pipeline-events; do
    gcloud pubsub topics delete "$topic" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $topic" || true
done

echo ""
echo -e "${BLUE}=== Step 3: Delete BigQuery Datasets ===${NC}"
for ds in odp_em fdp_em job_control odp_loa fdp_loa; do
    bq rm -r -f --project_id="$PROJECT_ID" "$ds" 2>/dev/null && echo "  Deleted: $ds" || true
done

echo ""
echo -e "${BLUE}=== Step 4: Delete GCS Buckets ===${NC}"
# Delete both manual and Terraform-created buckets
for bucket in \
    em-landing em-archive em-error em-temp \
    em-dev-landing em-dev-archive em-dev-error em-dev-temp \
    loa-landing loa-archive loa-error loa-temp \
    loa-dev-landing loa-dev-archive loa-dev-error loa-dev-temp \
    dataflow-templates em-dataflow-temp loa-dataflow-temp; do
    gsutil -m rm -r "gs://${PROJECT_ID}-${bucket}" 2>/dev/null && echo "  Deleted: gs://${PROJECT_ID}-${bucket}" || true
done

echo ""
echo -e "${BLUE}=== Step 5: Delete Terraform State Bucket ===${NC}"
gsutil -m rm -r "gs://gdw-terraform-state" 2>/dev/null && echo "  Deleted: gs://gdw-terraform-state" || true

echo ""
echo -e "${BLUE}=== Step 6: Delete Service Accounts ===${NC}"
# Delete all pipeline service accounts (both naming patterns)
for sa in \
    em-dataflow-sa em-dbt-sa em-composer-sa \
    em-dev-dataflow em-dev-dbt em-dev-composer \
    loa-dataflow-sa loa-dbt-sa loa-composer-sa \
    loa-dev-dataflow loa-dev-dbt loa-dev-composer; do
    gcloud iam service-accounts delete "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $sa" || true
done

echo ""
echo -e "${BLUE}=== Step 7: Delete Additional Pub/Sub Resources ===${NC}"
# Delete dead letter topics/subscriptions created by Terraform
for topic in em-file-notifications-dead-letter em-pipeline-events-dead-letter loa-file-notifications-dead-letter loa-pipeline-events-dead-letter; do
    gcloud pubsub topics delete "$topic" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted topic: $topic" || true
done

echo ""
echo -e "${GREEN}=============================================="
echo "✅ Full Reset Complete!"
echo "==============================================${NC}"
echo ""
echo "Next steps to redeploy:"
echo "  1. ./scripts/gcp/01_enable_services.sh"
echo "  2. ./scripts/gcp/02_create_state_bucket.sh"
echo "  3. ./scripts/gcp/03_create_infrastructure.sh all"
echo "  4. ./scripts/gcp/06_test_pipeline.sh em"
echo ""
echo "Or run everything at once:"
echo "  ./scripts/gcp/deploy_all.sh"

