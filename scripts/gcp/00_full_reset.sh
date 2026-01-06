#!/bin/bash
# =============================================================================
# FULL RESET: Delete Everything and Start Fresh
# =============================================================================
# Usage: ./scripts/gcp/00_full_reset.sh [--force]
#
# This script deletes ALL GCP resources to stop charges:
# 1. Dataflow jobs (running/pending)
# 2. Composer environments
# 3. GKE clusters
# 4. Cloud Run services
# 5. Pub/Sub topics and subscriptions
# 6. BigQuery datasets
# 7. GCS buckets
# 8. Service accounts
# 9. KMS keys (schedule for deletion)
# 10. Secret Manager secrets
# 11. Cloud Scheduler jobs
# 12. Terraform state
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

FORCE_DELETE="${1:-}"
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    echo "Run: gcloud config set project <PROJECT_ID>"
    exit 1
fi

echo -e "${RED}=============================================="
echo "⚠️  FULL RESET - Delete ALL GCP Resources"
echo "==============================================${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""
echo "This will delete:"
echo "  - Dataflow jobs (all running/pending)"
echo "  - Composer environments"
echo "  - GKE clusters"
echo "  - Cloud Run services"
echo "  - All Pub/Sub topics and subscriptions"
echo "  - All BigQuery datasets (odp_*, fdp_*, job_control)"
echo "  - All GCS buckets (em-*, loa-*, terraform-state)"
echo "  - All service accounts (em-*, loa-*)"
echo "  - KMS keys (scheduled for deletion)"
echo "  - Secret Manager secrets"
echo "  - Cloud Scheduler jobs"
echo "  - Terraform state"
echo ""

if [[ "$FORCE_DELETE" != "--force" ]]; then
    read -p "Type 'RESET' to confirm: " -r
    echo ""
    if [[ ! $REPLY == "RESET" ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

echo ""
echo -e "${BLUE}=== Step 1: Cancel Running Dataflow Jobs ===${NC}"
# Get all running/pending jobs and cancel them
for job_id in $(gcloud dataflow jobs list --project="$PROJECT_ID" --region="$REGION" --status=active --format="value(JOB_ID)" 2>/dev/null || true); do
    echo "  Cancelling job: $job_id"
    gcloud dataflow jobs cancel "$job_id" --project="$PROJECT_ID" --region="$REGION" --quiet 2>/dev/null || true
done
echo "  Dataflow jobs cancelled"

echo ""
echo -e "${BLUE}=== Step 2: Delete Composer Environments ===${NC}"
for env_name in $(gcloud composer environments list --project="$PROJECT_ID" --locations="$REGION" --format="value(name)" 2>/dev/null | grep -E "(em|loa)" || true); do
    echo "  Deleting Composer: $env_name"
    gcloud composer environments delete "$env_name" --project="$PROJECT_ID" --location="$REGION" --quiet 2>/dev/null || true
done
echo "  Composer environments deleted"

echo ""
echo -e "${BLUE}=== Step 3: Delete GKE Clusters ===${NC}"
for cluster in $(gcloud container clusters list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null | grep -E "(em|loa|composer)" || true); do
    zone=$(gcloud container clusters list --project="$PROJECT_ID" --filter="name=$cluster" --format="value(location)")
    echo "  Deleting GKE cluster: $cluster"
    gcloud container clusters delete "$cluster" --project="$PROJECT_ID" --zone="$zone" --quiet 2>/dev/null || true
done
echo "  GKE clusters deleted"

echo ""
echo -e "${BLUE}=== Step 4: Delete Cloud Run Services ===${NC}"
for service in $(gcloud run services list --project="$PROJECT_ID" --region="$REGION" --format="value(metadata.name)" 2>/dev/null | grep -E "(em|loa)" || true); do
    echo "  Deleting Cloud Run: $service"
    gcloud run services delete "$service" --project="$PROJECT_ID" --region="$REGION" --quiet 2>/dev/null || true
done
echo "  Cloud Run services deleted"

echo ""
echo -e "${BLUE}=== Step 5: Delete Pub/Sub Subscriptions ===${NC}"
for sub in em-file-notifications-sub em-pipeline-events-sub loa-file-notifications-sub loa-pipeline-events-sub; do
    gcloud pubsub subscriptions delete "$sub" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $sub" || true
done

echo ""
echo -e "${BLUE}=== Step 6: Delete Pub/Sub Topics ===${NC}"
for topic in em-file-notifications em-pipeline-events loa-file-notifications loa-pipeline-events; do
    gcloud pubsub topics delete "$topic" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $topic" || true
done

echo ""
echo -e "${BLUE}=== Step 7: Delete BigQuery Datasets ===${NC}"
for ds in odp_em fdp_em job_control odp_loa fdp_loa; do
    bq rm -r -f --project_id="$PROJECT_ID" "$ds" 2>/dev/null && echo "  Deleted: $ds" || true
done

echo ""
echo -e "${BLUE}=== Step 8: Delete GCS Buckets ===${NC}"
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
echo -e "${BLUE}=== Step 9: Delete Terraform State Bucket ===${NC}"
gsutil -m rm -r "gs://gdw-terraform-state" 2>/dev/null && echo "  Deleted: gs://gdw-terraform-state" || true

echo ""
echo -e "${BLUE}=== Step 10: Delete Service Accounts ===${NC}"
# Delete all pipeline service accounts (both naming patterns)
for sa in \
    em-dataflow-sa em-dbt-sa em-composer-sa \
    em-dev-dataflow em-dev-dbt em-dev-composer \
    loa-dataflow-sa loa-dbt-sa loa-composer-sa \
    loa-dev-dataflow loa-dev-dbt loa-dev-composer; do
    gcloud iam service-accounts delete "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $sa" || true
done

echo ""
echo -e "${BLUE}=== Step 11: Delete Additional Pub/Sub Resources ===${NC}"
# Delete dead letter topics/subscriptions created by Terraform
for topic in em-file-notifications-dead-letter em-pipeline-events-dead-letter loa-file-notifications-dead-letter loa-pipeline-events-dead-letter; do
    gcloud pubsub topics delete "$topic" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted topic: $topic" || true
done

echo ""
echo -e "${BLUE}=== Step 12: Delete Cloud Scheduler Jobs ===${NC}"
for job in $(gcloud scheduler jobs list --project="$PROJECT_ID" --location="$REGION" --format="value(name)" 2>/dev/null | grep -E "(em|loa)" || true); do
    echo "  Deleting scheduler job: $job"
    gcloud scheduler jobs delete "$job" --project="$PROJECT_ID" --location="$REGION" --quiet 2>/dev/null || true
done
echo "  Cloud Scheduler jobs deleted"

echo ""
echo -e "${BLUE}=== Step 13: Delete Secret Manager Secrets ===${NC}"
for secret in $(gcloud secrets list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null | grep -E "(em|loa)" || true); do
    echo "  Deleting secret: $secret"
    gcloud secrets delete "$secret" --project="$PROJECT_ID" --quiet 2>/dev/null || true
done
echo "  Secrets deleted"

echo ""
echo -e "${BLUE}=== Step 14: Schedule KMS Key Deletion (if any) ===${NC}"
# Note: KMS keys cannot be immediately deleted, only scheduled for destruction
for keyring in em-keyring loa-keyring pipeline-keyring; do
    for key in $(gcloud kms keys list --project="$PROJECT_ID" --location="$REGION" --keyring="$keyring" --format="value(name)" 2>/dev/null || true); do
        key_name=$(basename "$key")
        echo "  Scheduling destruction: $keyring/$key_name"
        gcloud kms keys versions destroy 1 --project="$PROJECT_ID" --location="$REGION" --keyring="$keyring" --key="$key_name" --quiet 2>/dev/null || true
    done
done
echo "  KMS keys scheduled for destruction (30-day hold)"

echo ""
echo -e "${BLUE}=== Step 15: Delete Cloud Functions ===${NC}"
for func in $(gcloud functions list --project="$PROJECT_ID" --regions="$REGION" --format="value(name)" 2>/dev/null | grep -E "(em|loa)" || true); do
    echo "  Deleting function: $func"
    gcloud functions delete "$func" --project="$PROJECT_ID" --region="$REGION" --quiet 2>/dev/null || true
done
echo "  Cloud Functions deleted"

echo ""
echo -e "${BLUE}=== Step 16: Delete Artifact Registry Repositories ===${NC}"
for repo in $(gcloud artifacts repositories list --project="$PROJECT_ID" --location="$REGION" --format="value(name)" 2>/dev/null | grep -E "(em|loa|pipeline)" || true); do
    echo "  Deleting repository: $repo"
    gcloud artifacts repositories delete "$repo" --project="$PROJECT_ID" --location="$REGION" --quiet 2>/dev/null || true
done
echo "  Artifact Registry repositories deleted"

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

