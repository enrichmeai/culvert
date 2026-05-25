#!/usr/bin/env bash
# =============================================================================
# gke_down.sh — Tear down ephemeral GKE cluster after testing
#
# Deletes only the GKE cluster. Preserves GCS, BigQuery, Pub/Sub (cheap/free).
# Run this IMMEDIATELY after E2E tests to stop costs.
#
# Usage: ./scripts/gcp/gke_down.sh [--all]
#   --all  Also delete GCS buckets, BigQuery datasets, Pub/Sub (full teardown)
# =============================================================================
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
ZONE="europe-west2-a"
CLUSTER_NAME="pipeline-cluster"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DELETE_ALL=false
[[ "${1:-}" == "--all" ]] && DELETE_ALL=true

echo -e "${RED}=== GKE Teardown ===${NC}"
echo "Project: $PROJECT_ID"
echo ""

# ── 1. Delete GKE cluster ──
if gcloud container clusters describe "$CLUSTER_NAME" --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null 2>&1; then
    echo -e "${YELLOW}Deleting cluster: $CLUSTER_NAME (~3-5 min)...${NC}"
    gcloud container clusters delete "$CLUSTER_NAME" \
        --zone "$ZONE" \
        --project "$PROJECT_ID" \
        --quiet
    echo -e "${GREEN}Cluster deleted${NC}"
else
    echo -e "${GREEN}Cluster already deleted${NC}"
fi
echo ""

# ── 2. Clean container images (keep only latest) ──
echo -e "${YELLOW}Cleaning old container images...${NC}"
REGISTRY="gcr.io/${PROJECT_ID}"
for REPO in generic-ingestion generic-transformation generic-dag-validator; do
    DIGESTS=$(gcloud container images list-tags "${REGISTRY}/${REPO}" \
        --format="get(digest)" --sort-by="~timestamp" 2>/dev/null || true)
    if [ -n "$DIGESTS" ]; then
        OLD=$(echo "$DIGESTS" | tail -n +2)
        COUNT=$(echo "$OLD" | grep -c "sha256:" || true)
        if [ "$COUNT" -gt 0 ]; then
            echo "  ${REPO}: deleting ${COUNT} old images..."
            echo "$OLD" | while read -r d; do
                [ -z "$d" ] && continue
                gcloud container images delete "${REGISTRY}/${REPO}@${d}" --quiet --force-delete-tags 2>/dev/null || true
            done
        fi
    fi
done
echo ""

# ── 3. Full teardown if --all ──
if $DELETE_ALL; then
    echo -e "${RED}Full teardown: deleting data resources...${NC}"

    # GCS buckets (keep terraform state)
    for bucket in $(gcloud storage buckets list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null); do
        if [[ "$bucket" == "gcp-pipeline-terraform-state" ]]; then
            echo -e "  ${GREEN}KEEPING:${NC} $bucket"
            continue
        fi
        echo "  Deleting: $bucket"
        gcloud storage rm --recursive "gs://$bucket/**" --project="$PROJECT_ID" 2>/dev/null || true
        gcloud storage buckets delete "gs://$bucket" --project="$PROJECT_ID" 2>/dev/null || true
    done

    # BigQuery
    for ds in $(bq ls --project_id="$PROJECT_ID" --format=prettyjson 2>/dev/null | python3 -c "import sys,json; [print(d['datasetReference']['datasetId']) for d in json.load(sys.stdin)]" 2>/dev/null); do
        echo "  Deleting dataset: $ds"
        bq rm -r -f --project_id="$PROJECT_ID" "$ds" 2>&1
    done

    # Pub/Sub
    for sub in $(gcloud pubsub subscriptions list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null); do
        gcloud pubsub subscriptions delete "$sub" --project="$PROJECT_ID" --quiet 2>/dev/null || true
    done
    for topic in $(gcloud pubsub topics list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null); do
        gcloud pubsub topics delete "$topic" --project="$PROJECT_ID" --quiet 2>/dev/null || true
    done

    echo -e "${GREEN}Full teardown complete${NC}"
    echo ""
fi

# ── Summary ──
echo -e "${GREEN}=============================================="
echo "  Teardown Complete"
echo "==============================================${NC}"
echo ""
if $DELETE_ALL; then
    echo "  Deleted: GKE cluster + all data resources"
    echo "  Kept:    Terraform state bucket"
else
    echo "  Deleted: GKE cluster + old container images"
    echo "  Kept:    GCS, BigQuery, Pub/Sub (free when idle)"
fi
echo ""
echo "  Monthly cost is now: ~£0"
echo "  To spin up again:    ./scripts/gcp/gke_up.sh --skip-data"
echo ""
