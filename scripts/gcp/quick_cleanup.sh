#!/bin/bash
# =============================================================================
# Quick Cleanup: Remove all test resources
# =============================================================================
# Removes all resources created by quick_deploy.sh
#
# Usage: ./scripts/gcp/quick_cleanup.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

echo "=============================================="
echo "Quick Cleanup - Remove All Test Resources"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "=============================================="
echo ""
echo -e "${YELLOW}WARNING: This will delete all test resources!${NC}"
read -p "Are you sure? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# -----------------------------------------------------------------------------
# Step 1: Delete GCS Buckets
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 1: Delete GCS Buckets${NC}"

BUCKETS=(
    "${PROJECT_ID}-generic-landing"
    "${PROJECT_ID}-generic-archive"
    "${PROJECT_ID}-generic-error"
    "${PROJECT_ID}-generic-landing"
    "${PROJECT_ID}-generic-archive"
    "${PROJECT_ID}-generic-error"
    "${PROJECT_ID}-dataflow-temp"
)

for bucket in "${BUCKETS[@]}"; do
    echo -n "  Deleting $bucket... "
    gsutil -m rm -r "gs://$bucket" 2>/dev/null && echo "✅" || echo "⚠️ (not found)"
done

# -----------------------------------------------------------------------------
# Step 2: Delete BigQuery Datasets
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 2: Delete BigQuery Datasets${NC}"

DATASETS=(
    "odp_generic"
    "fdp_generic"
    "odp_generic"
    "fdp_generic"
    "job_control"
)

for dataset in "${DATASETS[@]}"; do
    echo -n "  Deleting $dataset... "
    bq rm -r -f "${PROJECT_ID}:${dataset}" 2>/dev/null && echo "✅" || echo "⚠️ (not found)"
done

# -----------------------------------------------------------------------------
# Step 3: Delete Pub/Sub Subscriptions and Topics
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 3: Delete Pub/Sub Resources${NC}"

# Subscriptions first
SUBS=(
    "generic-file-notifications-sub"
    "generic-file-notifications-sub"
)

for sub in "${SUBS[@]}"; do
    echo -n "  Deleting subscription $sub... "
    gcloud pubsub subscriptions delete "$sub" --quiet 2>/dev/null && echo "✅" || echo "⚠️ (not found)"
done

# Then topics
TOPICS=(
    "generic-file-notifications"
    "generic-file-notifications"
    "generic-dlq"
    "generic-dlq"
)

for topic in "${TOPICS[@]}"; do
    echo -n "  Deleting topic $topic... "
    gcloud pubsub topics delete "$topic" --quiet 2>/dev/null && echo "✅" || echo "⚠️ (not found)"
done

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}=============================================="
echo "Cleanup Complete!"
echo "==============================================${NC}"
echo ""
echo "All test resources have been deleted."
echo "No ongoing charges will be incurred."
echo ""

