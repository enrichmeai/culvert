#!/usr/bin/env bash
# =============================================================================
# cleanup_stale_resources.sh — Delete stale/orphaned GCP resources
#
# Keeps: int environment (Composer, pipeline buckets, BQ datasets, Pub/Sub)
# Deletes: orphaned Composer buckets, Dataflow staging, stale BQ datasets, stale SA
#
# Usage: ./scripts/gcp/cleanup_stale_resources.sh
# =============================================================================
set -euo pipefail

PROJECT_ID="joseph-antony-aruja"
REGION="europe-west2"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${RED}=== GCP Stale Resource Cleanup ===${NC}"
echo "Project: $PROJECT_ID"
echo ""

# ── 1. Delete orphaned Composer GCS buckets (old Composer envs deleted but buckets remain) ──
echo -e "${YELLOW}Step 1: Deleting orphaned Composer GCS buckets${NC}"
ACTIVE_COMPOSER_BUCKET="europe-west2-generic-int-co-aeeea75a-bucket"

ORPHANED_COMPOSER_BUCKETS=(
    "europe-west2-generic-int-co-28f6bf22-bucket"
    "europe-west2-generic-int-co-3178e9e2-bucket"
    "europe-west2-generic-int-co-8a9eb4b5-bucket"
    "europe-west2-generic-int-co-9adb6d12-bucket"
    "europe-west2-generic-int-co-9f16f822-bucket"
)

for bucket in "${ORPHANED_COMPOSER_BUCKETS[@]}"; do
    echo -n "  Deleting gs://$bucket ... "
    if gcloud storage rm --recursive "gs://$bucket/**" --project="$PROJECT_ID" 2>/dev/null; then
        gcloud storage buckets delete "gs://$bucket" --project="$PROJECT_ID" 2>/dev/null && \
            echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}bucket shell remains (may need manual delete)${NC}"
    else
        # Try just deleting the empty bucket
        gcloud storage buckets delete "gs://$bucket" --project="$PROJECT_ID" 2>/dev/null && \
            echo -e "${GREEN}done (was empty)${NC}" || echo -e "${YELLOW}skipped (not found)${NC}"
    fi
done
echo ""

# ── 2. Delete Dataflow staging buckets (auto-created in multiple regions) ──
echo -e "${YELLOW}Step 2: Deleting Dataflow staging buckets${NC}"
DATAFLOW_BUCKETS=(
    "dataflow-staging-europe-west2-60906399045"
    "dataflow-staging-us-central1-60906399045"
    "dataflow-staging-us-east1-60906399045"
)

for bucket in "${DATAFLOW_BUCKETS[@]}"; do
    echo -n "  Deleting gs://$bucket ... "
    if gcloud storage rm --recursive "gs://$bucket/**" --project="$PROJECT_ID" 2>/dev/null; then
        gcloud storage buckets delete "gs://$bucket" --project="$PROJECT_ID" 2>/dev/null && \
            echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}bucket shell remains${NC}"
    else
        gcloud storage buckets delete "gs://$bucket" --project="$PROJECT_ID" 2>/dev/null && \
            echo -e "${GREEN}done (was empty)${NC}" || echo -e "${YELLOW}skipped (not found)${NC}"
    fi
done
echo ""

# ── 3. Delete stale BigQuery datasets (leftover from dbt schema bug) ──
echo -e "${YELLOW}Step 3: Deleting stale BigQuery datasets${NC}"
STALE_DATASETS=(
    "fdp_generic_fdp"
    "fdp_generic_staging"
)

for dataset in "${STALE_DATASETS[@]}"; do
    echo -n "  Deleting $dataset ... "
    bq rm -r -f --project_id="$PROJECT_ID" "$dataset" 2>/dev/null && \
        echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}skipped (not found)${NC}"
done
echo ""

# ── 4. Delete stale service account ──
echo -e "${YELLOW}Step 4: Deleting stale service account${NC}"
echo -n "  Deleting airflow-sa ... "
gcloud iam service-accounts delete "airflow-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="$PROJECT_ID" --quiet 2>/dev/null && \
    echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}skipped (not found)${NC}"
echo ""

# ── 5. Delete stale airflow-dags bucket (not used by current Composer) ──
echo -e "${YELLOW}Step 5: Deleting stale airflow-dags bucket${NC}"
echo -n "  Deleting gs://${PROJECT_ID}-airflow-dags ... "
if gcloud storage rm --recursive "gs://${PROJECT_ID}-airflow-dags/**" --project="$PROJECT_ID" 2>/dev/null; then
    gcloud storage buckets delete "gs://${PROJECT_ID}-airflow-dags" --project="$PROJECT_ID" 2>/dev/null && \
        echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}bucket shell remains${NC}"
else
    gcloud storage buckets delete "gs://${PROJECT_ID}-airflow-dags" --project="$PROJECT_ID" 2>/dev/null && \
        echo -e "${GREEN}done (was empty)${NC}" || echo -e "${YELLOW}skipped (not found)${NC}"
fi
echo ""

# ── 6. Delete stale Cloud Build artifacts from Composer bucket ──
echo -e "${YELLOW}Step 6: Cleaning stale Cloud Build artifacts${NC}"
COMPOSER_BUCKET=$(gcloud composer environments describe generic-int-composer \
    --location="$REGION" --project="$PROJECT_ID" \
    --format='value(config.dagGcsPrefix)' 2>/dev/null | sed 's|/dags$||') || true

if [ -n "$COMPOSER_BUCKET" ]; then
    BUILD_DIRS=$(gsutil ls "$COMPOSER_BUCKET/" 2>/dev/null | grep "\-build/$" || true)
    if [ -n "$BUILD_DIRS" ]; then
        COUNT=$(echo "$BUILD_DIRS" | wc -l | tr -d ' ')
        echo "  Found $COUNT stale build directories in Composer bucket"
        echo "$BUILD_DIRS" | while read dir; do
            echo -n "  Removing $(basename "$dir") ... "
            gsutil -m rm -r "$dir" 2>/dev/null && \
                echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}failed${NC}"
        done
    else
        echo -e "  ${YELLOW}No stale build directories found${NC}"
    fi
else
    echo -e "  ${YELLOW}Composer not found — skipping${NC}"
fi

echo ""
echo "  Cleaning Cloud Build source staging..."
gsutil -m rm -r "gs://${PROJECT_ID}_cloudbuild/source/" 2>/dev/null && \
    echo -e "  ${GREEN}Cloud Build source staging cleaned${NC}" || \
    echo -e "  ${YELLOW}No source staging to clean${NC}"
echo ""

# ── Summary: What's kept ──
echo -e "${GREEN}=== Resources KEPT (int environment) ===${NC}"
echo "  Composer:  generic-int-composer"
echo "  GKE:       europe-west2-generic-int-co-aeeea75a-gke (4 nodes)"
echo "  Buckets:   ${PROJECT_ID}-generic-int-{landing,archive,error,temp,segments}"
echo "  Buckets:   ${ACTIVE_COMPOSER_BUCKET}, ${PROJECT_ID}_cloudbuild, gcp-pipeline-terraform-state"
echo "  BigQuery:  odp_generic, fdp_generic, cdp_generic, job_control"
echo "  Pub/Sub:   generic-file-notifications, generic-pipeline-events (+dead-letter)"
echo "  SAs:       generic-int-dataflow, generic-int-dbt, generic-composer-sa, github-actions-deploy"
echo ""
echo -e "${RED}NOTE: Composer + GKE is your biggest cost (~\$300-500/month).${NC}"
echo -e "${RED}To stop ALL charges, run: gcloud composer environments delete generic-int-composer --location=$REGION${NC}"
echo -e "${RED}Then delete the GKE cluster if it persists.${NC}"
echo ""
echo -e "${GREEN}Cleanup complete.${NC}"
