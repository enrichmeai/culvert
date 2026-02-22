#!/bin/bash
# =============================================================================
# Publish GCP Pipeline Libraries: Build and Upload Python Libraries to PyPI
# =============================================================================
# Usage: ./scripts/publish_libraries.sh [pypi|testpypi]
#
# pypi: Publish to production PyPI (default)
# testpypi: Publish to TestPyPI
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Choose target repository name/URL
REPOSITORY_NAME="${1:-pypi}"
PROJECT_ROOT=$(pwd)

if [ "$REPOSITORY_NAME" == "testpypi" ]; then
    PYPI_URL="https://test.pypi.org/legacy/"
    echo -e "${YELLOW}Publishing to TestPyPI (GCP Pipeline Libraries)...${NC}"
else
    PYPI_URL="https://upload.pypi.org/legacy/"
    echo -e "${BLUE}Publishing to production PyPI (GCP Pipeline Libraries)...${NC}"
fi

LIB_ROOT="gcp-pipeline-libraries"
LIBRARIES=(
    "gcp-pipeline-core"
    "gcp-pipeline-beam"
    "gcp-pipeline-orchestration"
    "gcp-pipeline-transform"
    "gcp-pipeline-tester"
    "gcp-migration-framework"
)

# Use virtual environment python if available, otherwise fallback to system python
if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_ROOT/venv/bin/python"
else
    PYTHON_CMD="python3"
fi

# Check for twine
if ! $PYTHON_CMD -m twine --version &> /dev/null; then
    echo -e "${YELLOW}Installing twine for publishing...${NC}"
    $PYTHON_CMD -m pip install --upgrade twine build
fi

for lib in "${LIBRARIES[@]}"; do
    echo -e "\n${BLUE}>>> Processing $lib...${NC}"
    
    cd "$LIB_ROOT/$lib"
    
    # Clean old builds
    rm -rf dist/ build/ *.egg-info
    
    # Build package
    echo "  Building package..."
    $PYTHON_CMD -m build
    
    # Upload package
    echo "  Uploading to PyPI..."
    if [ "$REPOSITORY_NAME" == "testpypi" ]; then
        $PYTHON_CMD -m twine upload --repository testpypi dist/* --skip-existing
    else
        $PYTHON_CMD -m twine upload dist/* --skip-existing
    fi
    
    cd - > /dev/null
    echo -e "${GREEN}  ✅ Finished $lib${NC}"
done

echo -e "\n${GREEN}=============================================="
echo "Publishing process complete!"
echo "==============================================${NC}"
