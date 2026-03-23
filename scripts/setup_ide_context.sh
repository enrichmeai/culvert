#!/bin/bash
# =============================================================================
# Setup IDE Context: Initialize Monorepo Development Environment
# =============================================================================
# Creates a single venv at the project root with all libraries and deployments
# installed in editable mode. Provides full IDE support: "Go to Definition",
# real-time error checking, and import resolution across the entire monorepo.
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}>>> Initializing GCP Pipeline Reference Development Environment...${NC}"

# 1. Require Python 3.11 (apache-beam doesn't support 3.12+)
PYTHON=""
for candidate in python3.11 python3; do
    if command -v "$candidate" &> /dev/null; then
        ver=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        if [ "$ver" = "3.11" ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}Error: Python 3.11 is required (apache-beam doesn't support 3.12+).${NC}"
    echo -e "${RED}Install it with: brew install python@3.11${NC}"
    exit 1
fi

echo -e "${GREEN}Using: $($PYTHON --version 2>&1)${NC}"

# 2. Remove stale venvs if any exist alongside the canonical one
for stale in .venv .venv_3_11 .venv_junie_3_11 .venv_junie_3_11_beam253 .venv_tests venv311; do
    if [ -d "$PROJECT_ROOT/$stale" ]; then
        echo -e "${YELLOW}Removing stale venv: $stale${NC}"
        rm -rf "$PROJECT_ROOT/$stale"
    fi
done

# 3. Create single venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment (venv) with Python 3.11...${NC}"
    $PYTHON -m venv venv
else
    echo -e "${GREEN}Using existing virtual environment (venv).${NC}"
fi

# 3. Activate venv
source venv/bin/activate

# 4. Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
python3 -m pip install --upgrade pip --quiet

# 5. Install heavy dependencies first (avoids ResolutionTooDeep)
echo -e "${YELLOW}Installing core dependencies...${NC}"
python3 -m pip install --quiet \
    "apache-beam[gcp]==2.56.0" \
    "apache-airflow>=2.8.0" \
    "apache-airflow-providers-google>=10.1.0" \
    "dbt-bigquery>=1.7.0"

# 6. Install all libraries in editable mode (order matters: core first)
echo -e "${YELLOW}Installing libraries in editable mode...${NC}"

LIBRARIES=(
    "gcp-pipeline-core"
    "gcp-pipeline-beam"
    "gcp-pipeline-orchestration"
    "gcp-pipeline-transform"
    "gcp-pipeline-tester"
    "gcp-pipeline-framework"
)

for lib in "${LIBRARIES[@]}"; do
    LIB_PATH="$PROJECT_ROOT/gcp-pipeline-libraries/$lib"
    if [ -d "$LIB_PATH" ] && [ -f "$LIB_PATH/pyproject.toml" ]; then
        echo -e "  ${BLUE}Installing $lib...${NC}"
        python3 -m pip install -e "$LIB_PATH" --quiet --no-deps
    fi
done

# 7. Install deployments in editable mode
echo -e "${YELLOW}Installing deployments in editable mode...${NC}"

DEPLOYMENTS=(
    "original-data-to-bigqueryload"
    "data-pipeline-orchestrator"
    "bigquery-to-mapped-product"
    "fdp-to-consumable-product"
    "mainframe-segment-transform"
)

for dep in "${DEPLOYMENTS[@]}"; do
    DEP_PATH="$PROJECT_ROOT/deployments/$dep"
    if [ -d "$DEP_PATH" ] && [ -f "$DEP_PATH/pyproject.toml" ]; then
        echo -e "  ${BLUE}Installing $dep...${NC}"
        python3 -m pip install -e "$DEP_PATH" --quiet --no-deps
    fi
done

# 8. Install root package with dev dependencies (pytest, linters, etc.)
echo -e "${YELLOW}Installing dev tools...${NC}"
python3 -m pip install -e ".[dev]" --quiet

echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "Single venv at: ${BLUE}$PROJECT_ROOT/venv${NC}"
echo -e "All libraries and deployments installed in editable mode."
echo -e "\nTo activate this environment in your terminal, run:"
echo -e "${BLUE}source venv/bin/activate${NC}"
echo -e "${GREEN}================================================================${NC}"
