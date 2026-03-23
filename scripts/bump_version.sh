#!/usr/bin/env bash
# =============================================================================
# bump_version.sh — Single source of truth version updater
#
# Usage:
#   1. Edit the VERSION file at the repo root
#   2. Run: ./scripts/bump_version.sh
#
# This script reads VERSION and updates all locations that embed the version:
#   - Library __init__.py and pyproject.toml files
#   - Deployment __init__.py and pyproject.toml files
#   - Terraform Composer pypi_packages
#   - Vendored test copies
#
# Does NOT touch template snapshots under gcp-pipeline-framework/src/
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

VERSION_FILE="$PROJECT_ROOT/VERSION"
if [ ! -f "$VERSION_FILE" ]; then
    echo -e "${RED}ERROR: VERSION file not found at $VERSION_FILE${NC}"
    exit 1
fi

VERSION=$(tr -d '[:space:]' < "$VERSION_FILE")

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}ERROR: Invalid version format: '$VERSION' (expected X.Y.Z)${NC}"
    exit 1
fi

echo -e "${GREEN}Bumping all versions to: $VERSION${NC}"
echo ""

CHANGED=0

update_file() {
    local file="$1"
    local pattern="$2"
    local replacement="$3"
    local label="$4"

    if [ ! -f "$file" ]; then
        echo -e "  ${YELLOW}SKIP${NC} $label (file not found)"
        return
    fi

    if grep -q "$replacement" "$file" 2>/dev/null; then
        echo -e "  ${GREEN}OK${NC}   $label"
        return
    fi

    if grep -q "$pattern" "$file" 2>/dev/null; then
        sed -i '' "s|$pattern|$replacement|g" "$file"
        echo -e "  ${YELLOW}UPDATED${NC} $label"
        CHANGED=$((CHANGED + 1))
    else
        echo -e "  ${YELLOW}SKIP${NC} $label (pattern not found)"
    fi
}

# ── Library __init__.py files ──
echo "Libraries (__init__.py):"
LIBRARIES=(core beam orchestration transform tester)
for lib in "${LIBRARIES[@]}"; do
    init="$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-$lib/src/gcp_pipeline_${lib}/__init__.py"
    update_file "$init" \
        '__version__ = "[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"' \
        "__version__ = \"$VERSION\"" \
        "gcp-pipeline-$lib"
done

# Framework __init__.py (different path)
FRAMEWORK_INIT="$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-framework/src/gcp_pipeline_framework/__init__.py"
if [ -f "$FRAMEWORK_INIT" ] && grep -q '__version__' "$FRAMEWORK_INIT" 2>/dev/null; then
    update_file "$FRAMEWORK_INIT" \
        '__version__ = "[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"' \
        "__version__ = \"$VERSION\"" \
        "gcp-pipeline-framework"
fi
echo ""

# ── Library pyproject.toml files ──
echo "Libraries (pyproject.toml):"
ALL_LIBS=(core beam orchestration transform tester framework)
for lib in "${ALL_LIBS[@]}"; do
    toml="$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-$lib/pyproject.toml"
    update_file "$toml" \
        'version = "[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"' \
        "version = \"$VERSION\"" \
        "gcp-pipeline-$lib"
done
echo ""

# ── Deployment pyproject.toml files ──
echo "Deployments (pyproject.toml):"
DEPLOYMENTS=(
    original-data-to-bigqueryload
    data-pipeline-orchestrator
    bigquery-to-mapped-product
    fdp-to-consumable-product
    mainframe-segment-transform
    postgres-cdc-streaming
)
for dep in "${DEPLOYMENTS[@]}"; do
    toml="$PROJECT_ROOT/deployments/$dep/pyproject.toml"
    update_file "$toml" \
        'version = "[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"' \
        "version = \"$VERSION\"" \
        "$dep"
done
echo ""

# ── Deployment __init__.py files ──
echo "Deployments (__init__.py):"
INGESTION_INIT="$PROJECT_ROOT/deployments/original-data-to-bigqueryload/src/data_ingestion/__init__.py"
update_file "$INGESTION_INIT" \
    '__version__ = "[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"' \
    "__version__ = \"$VERSION\"" \
    "data_ingestion"
echo ""

# ── Vendored tester copy ──
echo "Vendored copies:"
VENDORED_TESTER="$PROJECT_ROOT/deployments/original-data-to-bigqueryload/tests/libs/gcp_pipeline_tester/__init__.py"
update_file "$VENDORED_TESTER" \
    '__version__ = "[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"' \
    "__version__ = \"$VERSION\"" \
    "vendored gcp_pipeline_tester"
echo ""

# ── Root pyproject.toml ──
echo "Root:"
update_file "$PROJECT_ROOT/pyproject.toml" \
    'version = "[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"' \
    "version = \"$VERSION\"" \
    "pyproject.toml"
echo ""

# ── Terraform Composer pypi_packages ──
echo "Terraform:"
TF_MAIN="$PROJECT_ROOT/infrastructure/terraform/systems/generic/main.tf"
if [ -f "$TF_MAIN" ]; then
    # Update gcp-pipeline-core version
    update_file "$TF_MAIN" \
        'gcp-pipeline-core.*= "==[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"' \
        "gcp-pipeline-core          = \"==$VERSION\"" \
        "Composer pypi: gcp-pipeline-core"
    # Update gcp-pipeline-orchestration version
    update_file "$TF_MAIN" \
        'gcp-pipeline-orchestration.*= "==[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"' \
        "gcp-pipeline-orchestration = \"==$VERSION\"" \
        "Composer pypi: gcp-pipeline-orchestration"
fi
echo ""

# ── Framework config pyproject.toml ──
echo "Framework config:"
FW_CONFIG="$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-framework/src/gcp_pipeline_framework/config/pyproject.toml"
update_file "$FW_CONFIG" \
    'version = "[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"' \
    "version = \"$VERSION\"" \
    "framework config pyproject"
echo ""

# ── Framework dependency pins (==X.Y.Z) ──
echo "Framework dependency pins:"
FW_TOML="$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-framework/pyproject.toml"
if [ -f "$FW_TOML" ]; then
    # Update all ==X.Y.Z pins to the new version
    OLD_PINS=$(grep -oP '==[0-9]+\.[0-9]+\.[0-9]+' "$FW_TOML" | head -1 | sed 's/==//')
    if [ -n "$OLD_PINS" ] && [ "$OLD_PINS" != "$VERSION" ]; then
        sed -i '' "s/==$OLD_PINS/==$VERSION/g" "$FW_TOML"
        echo -e "  ${YELLOW}UPDATED${NC} framework dependency pins ($OLD_PINS → $VERSION)"
        CHANGED=$((CHANGED + 1))
    else
        echo -e "  ${GREEN}OK${NC}   framework dependency pins"
    fi
fi
echo ""

# ── Summary ──
echo "=============================================="
if [ "$CHANGED" -eq 0 ]; then
    echo -e "${GREEN}All files already at $VERSION${NC}"
else
    echo -e "${YELLOW}Updated $CHANGED file(s) to $VERSION${NC}"
fi
echo "=============================================="
