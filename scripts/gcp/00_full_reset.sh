#!/bin/bash
# =============================================================================
# FULL RESET: Delete Everything and Start Fresh
# =============================================================================
# Usage: ./scripts/gcp/00_full_reset.sh [--force]
#
# This script deletes ALL GCP resources to stop charges:
# 1. GKE clusters (including pipeline-cluster)
# 2. Helm releases (Airflow)
# 3. Dataflow jobs (running/pending)
# 4. Composer environments
# 5. Cloud Run services
# 6. Pub/Sub topics and subscriptions
# 7. BigQuery datasets
# 8. GCS buckets
# 9. Service accounts (keeps github-actions-deploy for CI/CD)
# 10. GCS notifications
# 11. Container images in GCR
# 12. KMS keys (schedule for deletion)
# 13. Secret Manager secrets
# 14. Cloud Scheduler jobs
# 15. Terraform state
# 16. Cloud Build history and artifacts
# 17. IAM role bindings for deleted service accounts
#
# Last Updated: March 2026
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
ZONE="${REGION}-a"

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
echo "  - GKE clusters (pipeline-cluster)"
echo "  - Helm releases (Airflow)"
echo "  - Dataflow jobs (all running/pending)"
echo "  - Composer environments"
echo "  - Cloud Run services"
echo "  - All Pub/Sub topics and subscriptions"
echo "  - All BigQuery datasets (odp_*, fdp_*, cdp_*, job_control, error_tracking)"
echo "  - All GCS buckets (landing, archive, error, temp, segments, Composer, Dataflow staging)"
echo "  - All service accounts EXCEPT github-actions-deploy"
echo "  - IAM role bindings for deleted service accounts"
echo "  - Container images in GCR"
echo "  - KMS keys (scheduled for deletion)"
echo "  - Secret Manager secrets"
echo "  - Cloud Scheduler jobs"
echo "  - Terraform state"
echo "  - Cloud Build history and artifacts"
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
echo -e "${BLUE}=== Step 1: Delete GKE Clusters (MOST IMPORTANT - stops charges) ===${NC}"
# Delete pipeline-cluster first
if gcloud container clusters describe pipeline-cluster --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
    echo "  Deleting GKE cluster: pipeline-cluster (this takes ~5 minutes)"
    gcloud container clusters delete pipeline-cluster --zone="$ZONE" --project="$PROJECT_ID" --quiet --async 2>/dev/null || true
    echo "  Cluster deletion initiated (running async)"
else
    echo "  pipeline-cluster not found"
fi

# Delete any other GKE clusters
for cluster in $(gcloud container clusters list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null || true); do
    zone=$(gcloud container clusters list --project="$PROJECT_ID" --filter="name=$cluster" --format="value(location)")
    echo "  Deleting GKE cluster: $cluster"
    gcloud container clusters delete "$cluster" --project="$PROJECT_ID" --zone="$zone" --quiet --async 2>/dev/null || true
done
echo "  GKE clusters deletion initiated"

echo ""
echo -e "${BLUE}=== Step 2: Cancel Running Dataflow Jobs ===${NC}"
for job_id in $(gcloud dataflow jobs list --project="$PROJECT_ID" --region="$REGION" --status=active --format="value(JOB_ID)" 2>/dev/null || true); do
    echo "  Cancelling job: $job_id"
    gcloud dataflow jobs cancel "$job_id" --project="$PROJECT_ID" --region="$REGION" --quiet 2>/dev/null || true
done
echo "  Dataflow jobs cancelled"

echo ""
echo -e "${BLUE}=== Step 3: Delete Composer Environments ===${NC}"
for env_name in $(gcloud composer environments list --project="$PROJECT_ID" --locations="$REGION" --format="value(name)" 2>/dev/null || true); do
    echo "  Deleting Composer: $env_name"
    gcloud composer environments delete "$env_name" --project="$PROJECT_ID" --location="$REGION" --quiet --async 2>/dev/null || true
done
echo "  Composer environments deletion initiated"

echo ""
echo -e "${BLUE}=== Step 4: Delete Cloud Run Services ===${NC}"
for service in $(gcloud run services list --project="$PROJECT_ID" --region="$REGION" --format="value(metadata.name)" 2>/dev/null || true); do
    echo "  Deleting Cloud Run: $service"
    gcloud run services delete "$service" --project="$PROJECT_ID" --region="$REGION" --quiet 2>/dev/null || true
done
echo "  Cloud Run services deleted"

echo ""
echo -e "${BLUE}=== Step 5: Delete Pub/Sub Subscriptions ===${NC}"
# New naming convention
for sub in file-notifications-sub pipeline-events-sub; do
    gcloud pubsub subscriptions delete "$sub" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $sub" || true
done
# Old naming convention
for sub in generic-file-notifications-sub generic-pipeline-events-sub; do
    gcloud pubsub subscriptions delete "$sub" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $sub" || true
done

echo ""
echo -e "${BLUE}=== Step 6: Delete Pub/Sub Topics ===${NC}"
# New naming convention
for topic in file-notifications pipeline-events; do
    gcloud pubsub topics delete "$topic" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $topic" || true
done
# Old naming convention
for topic in generic-file-notifications generic-pipeline-events; do
    gcloud pubsub topics delete "$topic" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $topic" || true
done

echo ""
echo -e "${BLUE}=== Step 7: Delete BigQuery Datasets ===${NC}"
for ds in odp_generic fdp_generic fdp_generic_fdp fdp_generic_staging cdp_generic job_control error_tracking; do
    bq rm -r -f --project_id="$PROJECT_ID" "$ds" 2>/dev/null && echo "  Deleted: $ds" || true
done

echo ""
echo -e "${BLUE}=== Step 8: Delete GCS Buckets ===${NC}"
# Pipeline buckets (current naming: PROJECT_ID-generic-ENV-purpose)
for bucket in generic-int-landing generic-int-archive generic-int-error generic-int-temp generic-int-segments; do
    gsutil -m rm -r "gs://${PROJECT_ID}-${bucket}" 2>/dev/null && echo "  Deleted: gs://${PROJECT_ID}-${bucket}" || true
done
# CI/CD and Dataflow staging buckets
for bucket in airflow-dags dataflow-templates; do
    gsutil -m rm -r "gs://${PROJECT_ID}-${bucket}" 2>/dev/null && echo "  Deleted: gs://${PROJECT_ID}-${bucket}" || true
done
gsutil -m rm -r "gs://${PROJECT_ID}_cloudbuild" 2>/dev/null && echo "  Deleted: gs://${PROJECT_ID}_cloudbuild" || true
# Composer-managed buckets (auto-created by Cloud Composer)
for bucket in $(gsutil ls 2>/dev/null | grep "gs://europe-west2-generic-" || true); do
    gsutil -m rm -r "$bucket" 2>/dev/null && echo "  Deleted: $bucket" || true
done
# Dataflow staging buckets
for bucket in $(gsutil ls 2>/dev/null | grep "gs://dataflow-staging-" || true); do
    gsutil -m rm -r "$bucket" 2>/dev/null && echo "  Deleted: $bucket" || true
done
echo "  GCS buckets deleted"

echo ""
echo -e "${BLUE}=== Step 9: Delete Terraform State Bucket ===${NC}"
gsutil -m rm -r "gs://gcp-pipeline-terraform-state" 2>/dev/null && echo "  Deleted: gs://gcp-pipeline-terraform-state" || true
gsutil -m rm -r "gs://gdw-terraform-state" 2>/dev/null && echo "  Deleted: gs://gdw-terraform-state" || true

echo ""
echo -e "${BLUE}=== Step 10: Delete Service Accounts (keep github-actions-deploy) ===${NC}"
for sa in airflow-sa pipeline-sa generic-int-dataflow generic-int-dbt generic-composer-sa; do
    gcloud iam service-accounts delete "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted: $sa" || true
done
echo "  Kept: github-actions-deploy (required for CI/CD)"

echo ""
echo -e "${BLUE}=== Step 10b: Remove IAM Role Bindings for Deleted SAs ===${NC}"
# Remove all IAM bindings for pipeline SAs (deleting SA leaves orphaned bindings)
# Also removes orphaned bindings (deleted:serviceAccount:...?uid=...) for ALL SAs
# Keeps only: github-actions-deploy (live, no uid suffix), owner accounts, Google-managed agents

# Fetch current IAM policy once
IAM_POLICY=$(gcloud projects get-iam-policy "$PROJECT_ID" --format=json 2>/dev/null || echo "{}")

# 1. Remove bindings for explicitly listed pipeline SAs
PIPELINE_SAS=(
    "airflow-sa@${PROJECT_ID}.iam.gserviceaccount.com"
    "pipeline-sa@${PROJECT_ID}.iam.gserviceaccount.com"
    "generic-int-dataflow@${PROJECT_ID}.iam.gserviceaccount.com"
    "generic-int-dbt@${PROJECT_ID}.iam.gserviceaccount.com"
    "generic-composer-sa@${PROJECT_ID}.iam.gserviceaccount.com"
)

for sa_email in "${PIPELINE_SAS[@]}"; do
    member="serviceAccount:${sa_email}"
    roles=$(echo "$IAM_POLICY" | python3 -c "
import sys, json
policy = json.load(sys.stdin)
for binding in policy.get('bindings', []):
    if '$member' in binding.get('members', []):
        print(binding['role'])
" 2>/dev/null || true)

    for role in $roles; do
        gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
            --member="$member" --role="$role" --quiet 2>/dev/null \
            && echo "  Removed: $role from $sa_email" || true
    done
done

# 2. Remove ALL orphaned/deleted SA bindings (deleted:serviceAccount:...?uid=...)
echo "  Cleaning orphaned (deleted SA) bindings..."
ORPHANED_MEMBERS=$(echo "$IAM_POLICY" | python3 -c "
import sys, json
policy = json.load(sys.stdin)
seen = set()
for binding in policy.get('bindings', []):
    for member in binding.get('members', []):
        if member.startswith('deleted:') and member not in seen:
            seen.add(member)
            print(member + '|' + binding['role'])
" 2>/dev/null || true)

while IFS='|' read -r member role; do
    [ -z "$member" ] && continue
    gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
        --member="$member" --role="$role" --quiet 2>/dev/null \
        && echo "  Removed orphaned: $role from ${member##*:}" || true
done <<< "$ORPHANED_MEMBERS"

echo "  IAM bindings cleaned"

echo ""
echo -e "${BLUE}=== Step 11: Delete Container Images in GCR ===${NC}"
for image in airflow-custom generic-ingestion generic-transformation generic-dag-validator generic-cdp-transformation ingestion-pipeline transform-pipeline orchestrator segment-transform; do
    gcloud container images delete "gcr.io/${PROJECT_ID}/${image}" --force-delete-tags --quiet 2>/dev/null && echo "  Deleted: $image" || true
done
echo "  Container images deleted"

echo ""
echo -e "${BLUE}=== Step 12: Delete Dead Letter Topics ===${NC}"
for topic in file-notifications-dead-letter pipeline-events-dead-letter generic-file-notifications-dead-letter; do
    gcloud pubsub topics delete "$topic" --project="$PROJECT_ID" --quiet 2>/dev/null && echo "  Deleted topic: $topic" || true
done

echo ""
echo -e "${BLUE}=== Step 13: Delete Cloud Scheduler Jobs ===${NC}"
for job in $(gcloud scheduler jobs list --project="$PROJECT_ID" --location="$REGION" --format="value(name)" 2>/dev/null || true); do
    echo "  Deleting scheduler job: $job"
    gcloud scheduler jobs delete "$job" --project="$PROJECT_ID" --location="$REGION" --quiet 2>/dev/null || true
done
echo "  Cloud Scheduler jobs deleted"

echo ""
echo -e "${BLUE}=== Step 14: Delete Secret Manager Secrets ===${NC}"
for secret in $(gcloud secrets list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null || true); do
    echo "  Deleting secret: $secret"
    gcloud secrets delete "$secret" --project="$PROJECT_ID" --quiet 2>/dev/null || true
done
echo "  Secrets deleted"

echo ""
echo -e "${BLUE}=== Step 15: Schedule KMS Key Deletion (if any) ===${NC}"
for keyring in pipeline-keyring; do
    for key in $(gcloud kms keys list --project="$PROJECT_ID" --location="$REGION" --keyring="$keyring" --format="value(name)" 2>/dev/null || true); do
        key_name=$(basename "$key")
        echo "  Scheduling destruction: $keyring/$key_name"
        gcloud kms keys versions destroy 1 --project="$PROJECT_ID" --location="$REGION" --keyring="$keyring" --key="$key_name" --quiet 2>/dev/null || true
    done
done
echo "  KMS keys scheduled for destruction (30-day hold)"

echo ""
echo -e "${BLUE}=== Step 16: Delete Cloud Functions ===${NC}"
for func in $(gcloud functions list --project="$PROJECT_ID" --regions="$REGION" --format="value(name)" 2>/dev/null || true); do
    echo "  Deleting function: $func"
    gcloud functions delete "$func" --project="$PROJECT_ID" --region="$REGION" --quiet 2>/dev/null || true
done
echo "  Cloud Functions deleted"

echo ""
echo -e "${BLUE}=== Step 17: Delete Artifact Registry Repositories ===${NC}"
for repo in $(gcloud artifacts repositories list --project="$PROJECT_ID" --location="$REGION" --format="value(name)" 2>/dev/null || true); do
    echo "  Deleting repository: $repo"
    gcloud artifacts repositories delete "$repo" --project="$PROJECT_ID" --location="$REGION" --quiet 2>/dev/null || true
done
echo "  Artifact Registry repositories deleted"

echo ""
echo -e "${BLUE}=== Step 18: Delete Cloud Build History ===${NC}"
# Delete the Cloud Build source/logs bucket
gsutil -m rm -r "gs://${PROJECT_ID}_cloudbuild" 2>/dev/null && echo "  Deleted: gs://${PROJECT_ID}_cloudbuild" || true
# Cancel any running builds
for build_id in $(gcloud builds list --region=global --ongoing --format="value(id)" 2>/dev/null || true); do
    echo "  Cancelling build: $build_id"
    gcloud builds cancel "$build_id" --region=global --quiet 2>/dev/null || true
done
echo "  Cloud Build cleaned up"
echo "  Note: Build history is retained by GCP and cannot be deleted via CLI."
echo "  To remove it, disable and re-enable the Cloud Build API:"
echo "    gcloud services disable cloudbuild.googleapis.com --force"
echo "    gcloud services enable cloudbuild.googleapis.com"

echo ""
echo -e "${GREEN}=============================================="
echo "✅ Full Reset Complete!"
echo "==============================================${NC}"
echo ""
echo "Note: GKE cluster deletion runs async and may take ~5 minutes."
echo "Check status with: gcloud container clusters list"
echo ""
echo "Next steps to redeploy EVERYTHING from scratch:"
echo ""
echo "  # Option 1: GKE-based deployment (RECOMMENDED)"
echo "  ./scripts/gcp/setup_gke_infrastructure.sh"
echo ""
echo "  # Then build custom Airflow image"
echo "  cd infrastructure/k8s/airflow"
echo "  gcloud builds submit --tag gcr.io/\${PROJECT_ID}/airflow-custom:latest ."
echo ""
echo "  # Then install Airflow on GKE"
echo "  helm install airflow apache-airflow/airflow \\"
echo "    --namespace airflow --create-namespace \\"
echo "    --version 1.11.0 \\"
echo "    --set images.airflow.repository=gcr.io/\${PROJECT_ID}/airflow-custom \\"
echo "    --set images.airflow.tag=latest \\"
echo "    --set executor=KubernetesExecutor \\"
echo "    --set webserver.service.type=LoadBalancer"
echo ""
echo "  # Deploy DAGs"
echo "  gsutil -m rsync -r deployments/data-pipeline-orchestrator/dags/ gs://\${PROJECT_ID}-airflow-dags/"
echo ""
echo "  # Option 2: Legacy Cloud Composer setup"
echo "  ./scripts/gcp/deploy_all.sh"
echo ""

