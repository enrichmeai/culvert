#!/bin/bash
# Full cleanup script for failed GCP deployments
set -e
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"
echo "=============================================="
echo "  GCP Full Cleanup Script"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""
echo "=== Step 1: Delete Composer Environments ==="
gcloud composer environments delete generic-dev-composer --location=$REGION --quiet 2>/dev/null || echo "generic-dev-composer not found"
gcloud composer environments delete generic-dev-composer --location=$REGION --quiet 2>/dev/null || echo "generic-dev-composer not found"
echo ""
echo "=== Step 2: Delete GKE Clusters ==="
for cluster in $(gcloud container clusters list --format="value(name)" 2>/dev/null | grep -E "(generic|generic|composer)" || true); do
    zone=$(gcloud container clusters list --filter="name=$cluster" --format="value(location)")
    echo "Deleting cluster: $cluster"
    gcloud container clusters delete "$cluster" --zone="$zone" --quiet || true
done
echo ""
echo "=== Step 3: Delete Pub/Sub ==="
gcloud pubsub subscriptions delete generic-file-notifications-sub --quiet 2>/dev/null || true
gcloud pubsub subscriptions delete generic-file-notifications-sub --quiet 2>/dev/null || true
gcloud pubsub topics delete generic-file-notifications --quiet 2>/dev/null || true
gcloud pubsub topics delete generic-file-notifications-dead-letter --quiet 2>/dev/null || true
gcloud pubsub topics delete generic-file-notifications --quiet 2>/dev/null || true
gcloud pubsub topics delete generic-file-notifications-dead-letter --quiet 2>/dev/null || true
echo ""
echo "=== Step 4: Delete BigQuery Datasets ==="
bq rm -r -f odp_generic 2>/dev/null || true
bq rm -r -f fdp_generic 2>/dev/null || true
bq rm -r -f odp_generic 2>/dev/null || true
bq rm -r -f fdp_generic 2>/dev/null || true
bq rm -r -f job_control 2>/dev/null || true
echo ""
echo "=== Step 5: Delete GCS Buckets ==="
for bucket in $(gsutil ls 2>/dev/null | grep -E "(generic-dev|generic-dev)" || true); do
    echo "Deleting bucket: $bucket"
    gsutil -m rm -r "$bucket" 2>/dev/null || true
done
echo ""
echo "=== Step 6: Delete Service Accounts ==="
for sa in generic-dev-dataflow generic-dev-dbt generic-composer-sa generic-pipeline-sa generic-composer-sa; do
    gcloud iam service-accounts delete "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" --quiet 2>/dev/null || true
done
echo ""
echo "=== Step 7: Clear Terraform Locks ==="
gsutil rm -f gs://gdw-terraform-state/generic/staging/default.tflock 2>/dev/null || true
gsutil rm -f gs://gdw-terraform-state/generic/staging/default.tflock 2>/dev/null || true
echo ""
echo "=== Cleanup Complete! ==="
