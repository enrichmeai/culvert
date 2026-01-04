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
gcloud composer environments delete em-dev-composer --location=$REGION --quiet 2>/dev/null || echo "em-dev-composer not found"
gcloud composer environments delete loa-dev-composer --location=$REGION --quiet 2>/dev/null || echo "loa-dev-composer not found"
echo ""
echo "=== Step 2: Delete GKE Clusters ==="
for cluster in $(gcloud container clusters list --format="value(name)" 2>/dev/null | grep -E "(em|loa|composer)" || true); do
    zone=$(gcloud container clusters list --filter="name=$cluster" --format="value(location)")
    echo "Deleting cluster: $cluster"
    gcloud container clusters delete "$cluster" --zone="$zone" --quiet || true
done
echo ""
echo "=== Step 3: Delete Pub/Sub ==="
gcloud pubsub subscriptions delete em-file-notifications-sub --quiet 2>/dev/null || true
gcloud pubsub subscriptions delete loa-file-notifications-sub --quiet 2>/dev/null || true
gcloud pubsub topics delete em-file-notifications --quiet 2>/dev/null || true
gcloud pubsub topics delete em-file-notifications-dead-letter --quiet 2>/dev/null || true
gcloud pubsub topics delete loa-file-notifications --quiet 2>/dev/null || true
gcloud pubsub topics delete loa-file-notifications-dead-letter --quiet 2>/dev/null || true
echo ""
echo "=== Step 4: Delete BigQuery Datasets ==="
bq rm -r -f odp_em 2>/dev/null || true
bq rm -r -f fdp_em 2>/dev/null || true
bq rm -r -f odp_loa 2>/dev/null || true
bq rm -r -f fdp_loa 2>/dev/null || true
bq rm -r -f job_control 2>/dev/null || true
echo ""
echo "=== Step 5: Delete GCS Buckets ==="
for bucket in $(gsutil ls 2>/dev/null | grep -E "(em-dev|loa-dev)" || true); do
    echo "Deleting bucket: $bucket"
    gsutil -m rm -r "$bucket" 2>/dev/null || true
done
echo ""
echo "=== Step 6: Delete Service Accounts ==="
for sa in em-dev-dataflow em-dev-dbt em-composer-sa loa-pipeline-sa loa-composer-sa; do
    gcloud iam service-accounts delete "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" --quiet 2>/dev/null || true
done
echo ""
echo "=== Step 7: Clear Terraform Locks ==="
gsutil rm -f gs://gdw-terraform-state/em/staging/default.tflock 2>/dev/null || true
gsutil rm -f gs://gdw-terraform-state/loa/staging/default.tflock 2>/dev/null || true
echo ""
echo "=== Cleanup Complete! ==="
