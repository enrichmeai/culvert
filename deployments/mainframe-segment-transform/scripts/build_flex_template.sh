#!/usr/bin/env bash
# =============================================================================
# Build Dataflow Flex Template (locally via Cloud Build)
# =============================================================================
# Builds the Docker image and uploads the Flex Template spec to GCS.
# No GitHub Actions needed — runs entirely from your terminal.
#
# Usage:
#   ./scripts/build_flex_template.sh [project_id] [version]
# =============================================================================
set -euo pipefail

PROJECT_ID="${1:-joseph-antony-aruja}"
VERSION="${2:-1.0.29}"
REPO_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"

echo "============================================"
echo "  Build Dataflow Flex Template"
echo "============================================"
echo "  Project:  ${PROJECT_ID}"
echo "  Version:  ${VERSION}"
echo "============================================"
echo ""

cd "${REPO_DIR}"

gcloud builds submit \
    --project="${PROJECT_ID}" \
    --config=deployments/mainframe-segment-transform/cloudbuild.yaml \
    --substitutions="_LIBRARY_VERSION=${VERSION}" \
    .

echo ""
echo "============================================"
echo "  Build complete"
echo "============================================"
echo "  Image:    gcr.io/${PROJECT_ID}/generic-segment-transform:${VERSION}"
echo "  Template: gs://${PROJECT_ID}-generic-int-segments/templates/segment_transform.json"
echo "============================================"
