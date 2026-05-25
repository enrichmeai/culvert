#!/usr/bin/env bash
# =============================================================================
# cleanup_builds.sh — Delete redundant Cloud Build artifacts and old container images
#
# Keeps: latest tagged image per repo (e.g., 1.0.29) + latest tag
# Deletes: all untagged images, old tagged versions, stale repos, Cloud Build source archives
#
# Usage: ./scripts/gcp/cleanup_builds.sh [--dry-run]
# =============================================================================
set -euo pipefail

PROJECT_ID="joseph-antony-aruja"
REGISTRY="gcr.io/${PROJECT_ID}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

DRY_RUN=false
FORCE=false
for arg in "$@"; do
    [[ "$arg" == "--dry-run" ]] && DRY_RUN=true
    [[ "$arg" == "--force" ]] && FORCE=true
done

if $DRY_RUN; then
    echo -e "${CYAN}=== DRY RUN — no deletions will be performed ===${NC}"
else
    echo -e "${RED}=== Cloud Build & Container Image Cleanup ===${NC}"
    if ! $FORCE; then
        echo -e "${YELLOW}This will delete old images and build artifacts. Press Ctrl+C to abort.${NC}"
        echo ""
        read -p "Continue? (y/N) " confirm
        [[ "$confirm" != "y" && "$confirm" != "Y" ]] && echo "Aborted." && exit 0
    fi
fi
echo "Project: $PROJECT_ID"
echo ""

TOTAL_DELETED=0
TOTAL_SKIPPED=0

# ── Helper: clean a single image repo, keeping only the latest tagged image ──
cleanup_image_repo() {
    local repo="$1"
    local repo_name
    repo_name=$(basename "$repo")

    echo -e "${YELLOW}Cleaning ${repo_name}...${NC}"

    # Get all digests with their tags, sorted newest first
    local digests
    digests=$(gcloud container images list-tags "${REGISTRY}/${repo_name}" \
        --format="get(digest,tags,timestamp.datetime)" \
        --sort-by="~timestamp" 2>/dev/null || true)

    if [[ -z "$digests" ]]; then
        echo -e "  ${YELLOW}No images found${NC}"
        return
    fi

    local kept=false
    local count=0
    local deleted=0

    while IFS=$'\t' read -r digest tags timestamp; do
        count=$((count + 1))

        # Keep the first image (newest) — it has the latest version tag
        if ! $kept; then
            echo -e "  ${GREEN}KEEP${NC}: ${digest:0:12} [${tags:-untagged}] ${timestamp}"
            kept=true
            TOTAL_SKIPPED=$((TOTAL_SKIPPED + 1))
            continue
        fi

        # Delete everything else
        local full_ref="${REGISTRY}/${repo_name}@${digest}"
        if $DRY_RUN; then
            echo -e "  ${CYAN}WOULD DELETE${NC}: ${digest:0:12} [${tags:-untagged}] ${timestamp}"
        else
            echo -n "  Deleting ${digest:0:12} [${tags:-untagged}]... "
            if gcloud container images delete "$full_ref" --quiet --force-delete-tags 2>/dev/null; then
                echo -e "${GREEN}done${NC}"
            else
                echo -e "${RED}failed${NC}"
            fi
        fi
        deleted=$((deleted + 1))
        TOTAL_DELETED=$((TOTAL_DELETED + 1))
    done <<< "$digests"

    echo -e "  Summary: kept 1, ${deleted} to delete (of ${count} total)"
    echo ""
}

# ── 1. Clean active image repos (keep latest only) ──
echo -e "${RED}=== Step 1: Clean Container Images (keep latest only) ===${NC}"
echo ""

ACTIVE_REPOS=(
    "generic-ingestion"
    "generic-transformation"
    "generic-dag-validator"
)

for repo in "${ACTIVE_REPOS[@]}"; do
    cleanup_image_repo "$repo"
done

# ── 2. Delete stale/unused image repos entirely ──
echo -e "${RED}=== Step 2: Delete Stale Image Repos ===${NC}"
echo ""

STALE_REPOS=(
    "airflow-custom"
    "generic-cdp-transformation"
)

for repo_name in "${STALE_REPOS[@]}"; do
    echo -e "${YELLOW}Deleting entire repo: ${repo_name}${NC}"

    digests=$(gcloud container images list-tags "${REGISTRY}/${repo_name}" \
        --format="get(digest)" 2>/dev/null || true)

    if [[ -z "$digests" ]]; then
        echo -e "  ${YELLOW}Already empty${NC}"
        continue
    fi

    stale_count=0
    while IFS= read -r digest; do
        [[ -z "$digest" ]] && continue
        stale_count=$((stale_count + 1))
        full_ref="${REGISTRY}/${repo_name}@${digest}"
        if $DRY_RUN; then
            echo -e "  ${CYAN}WOULD DELETE${NC}: ${digest:0:12}"
        else
            echo -n "  Deleting ${digest:0:12}... "
            gcloud container images delete "$full_ref" --quiet --force-delete-tags 2>/dev/null && \
                echo -e "${GREEN}done${NC}" || echo -e "${RED}failed${NC}"
        fi
        TOTAL_DELETED=$((TOTAL_DELETED + 1))
    done <<< "$digests"

    echo -e "  Deleted ${stale_count} images from ${repo_name}"
    echo ""
done

# ── 3. Clean Cloud Build source archives ──
echo -e "${RED}=== Step 3: Clean Cloud Build Source Archives ===${NC}"
echo ""

CLOUDBUILD_BUCKET="gs://${PROJECT_ID}_cloudbuild"
echo -e "${YELLOW}Cleaning ${CLOUDBUILD_BUCKET}...${NC}"

# List all objects with their sizes
bucket_size=$(gcloud storage du "${CLOUDBUILD_BUCKET}/" --summarize 2>/dev/null | awk '{print $1}' || echo "0")
bucket_size_mb=$((bucket_size / 1024 / 1024))
echo "  Current size: ~${bucket_size_mb} MB"

# List objects, keep only the 3 newest source archives
objects=$(gcloud storage ls -l "${CLOUDBUILD_BUCKET}/source/" 2>/dev/null | grep -v "TOTAL:" | sort -k2 -r || true)
object_count=$(echo "$objects" | grep -c "gs://" || true)

if [[ "$object_count" -gt 3 ]]; then
    echo "  Found ${object_count} source archives, keeping 3 newest"

    # Get objects to delete (skip first 3)
    to_delete=$(echo "$objects" | grep "gs://" | tail -n +4 | awk '{print $NF}')
    delete_count=$(echo "$to_delete" | grep -c "gs://" || true)

    if [[ "$delete_count" -gt 0 ]]; then
        if $DRY_RUN; then
            echo -e "  ${CYAN}WOULD DELETE${NC}: ${delete_count} old source archives"
        else
            echo "$to_delete" | while read -r obj; do
                [[ -z "$obj" ]] && continue
                gcloud storage rm "$obj" 2>/dev/null || true
            done
            echo -e "  ${GREEN}Deleted ${delete_count} old source archives${NC}"
        fi
        TOTAL_DELETED=$((TOTAL_DELETED + delete_count))
    fi
else
    echo -e "  ${GREEN}Only ${object_count} archives, nothing to clean${NC}"
fi

# Clean logs
log_objects=$(gcloud storage ls "${CLOUDBUILD_BUCKET}/logs/" 2>/dev/null | wc -l || echo "0")
if [[ "$log_objects" -gt 10 ]]; then
    echo "  Found ${log_objects} build logs"
    # Keep last 5 logs
    logs_to_delete=$(gcloud storage ls -l "${CLOUDBUILD_BUCKET}/logs/" 2>/dev/null | grep "gs://" | sort -k2 -r | tail -n +6 | awk '{print $NF}')
    logs_delete_count=$(echo "$logs_to_delete" | grep -c "gs://" || true)

    if [[ "$logs_delete_count" -gt 0 ]]; then
        if $DRY_RUN; then
            echo -e "  ${CYAN}WOULD DELETE${NC}: ${logs_delete_count} old build logs"
        else
            echo "$logs_to_delete" | while read -r obj; do
                [[ -z "$obj" ]] && continue
                gcloud storage rm "$obj" 2>/dev/null || true
            done
            echo -e "  ${GREEN}Deleted ${logs_delete_count} old build logs${NC}"
        fi
    fi
fi

echo ""

# ── 4. Auto-configure lifecycle on Cloud Build bucket ──
echo -e "${RED}=== Step 4: Set Lifecycle Policy (auto-delete after 7 days) ===${NC}"
echo ""

LIFECYCLE_JSON=$(cat <<'JSONEOF'
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 7}
    }
  ]
}
JSONEOF
)

if $DRY_RUN; then
    echo -e "  ${CYAN}WOULD SET${NC}: 7-day auto-delete lifecycle on ${CLOUDBUILD_BUCKET}"
else
    LIFECYCLE_FILE=$(mktemp /tmp/lifecycle-XXXXXX.json)
    echo "$LIFECYCLE_JSON" > "$LIFECYCLE_FILE"
    if gcloud storage buckets update "${CLOUDBUILD_BUCKET}" --lifecycle-file="$LIFECYCLE_FILE" 2>/dev/null; then
        echo -e "  ${GREEN}Set 7-day auto-delete lifecycle on ${CLOUDBUILD_BUCKET}${NC}"
    else
        echo -e "  ${RED}Failed to set lifecycle (may need storage.admin permissions)${NC}"
    fi
    rm -f "$LIFECYCLE_FILE"
fi

echo ""

# ── Summary ──
echo -e "${RED}=== Cleanup Summary ===${NC}"
if $DRY_RUN; then
    echo -e "  Mode:           ${CYAN}DRY RUN${NC}"
    echo -e "  Would delete:   ${TOTAL_DELETED} items"
    echo -e "  Would keep:     ${TOTAL_SKIPPED} items (latest per repo)"
    echo ""
    echo -e "  Run without --dry-run to execute deletions."
else
    echo -e "  Deleted:        ${TOTAL_DELETED} items"
    echo -e "  Kept:           ${TOTAL_SKIPPED} items (latest per repo)"
    echo -e "  Lifecycle:      7-day auto-delete on cloudbuild bucket"
fi
echo ""
echo "Done."
