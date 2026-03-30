#!/usr/bin/env bash
# =============================================================================
# Teardown CDP Segment Transform Infrastructure
# =============================================================================
# Removes only what setup_cdp_segment_infra.sh created:
#   - BigQuery: cdp_generic, job_control datasets
#   - GCS: segments bucket
#   - GCR: segment transform Docker images
#   - Active Dataflow segment jobs
#
# Usage:
#   ./scripts/gcp/teardown_cdp_segment_infra.sh [--force]
# =============================================================================
set -euo pipefail

FORCE=false
PROJECT_ID="${1:-joseph-antony-aruja}"
ENV="${2:-int}"
[[ "${1:-}" == "--force" ]] && FORCE=true && PROJECT_ID="joseph-antony-aruja"

BUCKET="${PROJECT_ID}-generic-${ENV}-segments"

echo "============================================"
echo "  CDP Segment — Teardown"
echo "============================================"
echo "  cdp_generic, job_control, gs://${BUCKET}"
echo "============================================"

if [ "${FORCE}" != true ]; then
    read -rp "Type TEARDOWN to confirm: " CONFIRM
    [[ "${CONFIRM}" != "TEARDOWN" ]] && echo "Aborted." && exit 1
fi

echo ""

# Cancel active Dataflow jobs
echo "=== Cancelling segment Dataflow jobs ==="
gcloud dataflow jobs list \
    --project="${PROJECT_ID}" --region="europe-west2" \
    --status=active --filter="name:segment-*" \
    --format="value(JOB_ID)" 2>/dev/null | while read -r JOB_ID; do
    echo "  Cancelling: ${JOB_ID}"
    gcloud dataflow jobs cancel "${JOB_ID}" \
        --project="${PROJECT_ID}" --region="europe-west2" 2>/dev/null || true
done
echo ""

# Delete BigQuery datasets
echo "=== Deleting BigQuery datasets ==="
for DS in cdp_generic job_control; do
    if bq --project_id="${PROJECT_ID}" show "${DS}" &>/dev/null; then
        bq --project_id="${PROJECT_ID}" rm -r -f -d "${PROJECT_ID}:${DS}"
        echo "  Deleted: ${DS}"
    else
        echo "  Not found: ${DS}"
    fi
done
echo ""

# Delete GCS bucket
echo "=== Deleting GCS bucket ==="
if gsutil ls -b "gs://${BUCKET}" &>/dev/null; then
    gsutil -m rm -r "gs://${BUCKET}" 2>/dev/null || true
    echo "  Deleted: gs://${BUCKET}"
else
    echo "  Not found: gs://${BUCKET}"
fi
echo ""

# Delete GCR images
echo "=== Deleting GCR images ==="
gcloud container images list-tags "gcr.io/${PROJECT_ID}/generic-segment-transform" \
    --format="value(digest)" 2>/dev/null | while read -r DIGEST; do
    gcloud container images delete "gcr.io/${PROJECT_ID}/generic-segment-transform@${DIGEST}" \
        --force-delete-tags --quiet 2>/dev/null || true
done
echo "  Done."
echo ""

echo "============================================"
echo "  Teardown complete."
echo "============================================"
