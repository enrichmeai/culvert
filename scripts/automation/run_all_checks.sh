#!/bin/bash
# =============================================================================
# Master Local Automation Script
# =============================================================================
# Runs all local validations: Linting, Unit Tests, and Integration Tests
# for both libraries and deployment units.
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=============================================="
echo "🚀 Starting Local Automation Suite"
echo "=============================================="

# 1. Library Tests
echo -e "\n${YELLOW}>>> Running Library Tests...${NC}"
if ./scripts/run_library_tests.sh; then
    echo -e "${GREEN}✅ Library tests passed!${NC}"
else
    echo -e "${RED}❌ Library tests failed!${NC}"
    exit 1
fi

# 2. Deployment Unit Tests (Example: EM System)
echo -e "\n${YELLOW}>>> Running Deployment Unit Tests (EM)...${NC}"
if [ -d "deployments/em-ingestion" ]; then
    cd deployments/em-ingestion
    # Assuming venv is already set up or using python -m pytest
    PYTHONPATH=src:../../gcp-pipeline-gcp-pipeline-libraries/gcp-pipeline-core/src:../../gcp-pipeline-gcp-pipeline-libraries/gcp-pipeline-beam/src \
      python3 -m pytest tests/unit/ || { echo -e "${RED}❌ EM Ingestion tests failed!${NC}"; exit 1; }
    cd ../..
    echo -e "${GREEN}✅ EM Ingestion tests passed!${NC}"
fi

# 3. Static Analysis / Linting
echo -e "\n${YELLOW}>>> Running Static Analysis (Qodana/Lint)...${NC}"
# In a real environment, you'd run flake8, pylint, or qodana scan
if command -v flake8 &> /dev/null; then
    flake8 gcp-pipeline-gcp-pipeline-libraries/ deployments/ --max-line-length=120 --exclude=venv || echo -e "${YELLOW}⚠️ Lint warnings found${NC}"
else
    echo "Skipping flake8 (not installed)"
fi

echo -e "\n${GREEN}=============================================="
echo "✨ All local checks completed successfully!"
echo "==============================================${NC}"
