#!/bin/bash
# =============================================================================
# Setup IDE Context: Initialize Monorepo Development Environment
# =============================================================================
# This script automates the setup for full IDE context help, "Go to Definition",
# and real-time error checking across all libraries and deployments.
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}>>> Initializing GCP Migration Framework Development Environment...${NC}"

# 1. Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed.${NC}"
    exit 1
fi

# 2. Create Virtual Environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment (venv)...${NC}"
    python3 -m venv venv
else
    echo -e "${GREEN}Using existing virtual environment (venv).${NC}"
fi

# 3. Activate venv
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# 4. Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# 5. Install in Editable Mode
echo -e "${YELLOW}Installing monorepo in editable mode with dev dependencies...${NC}"
echo -e "${BLUE}(This links all gcp-pipeline-* libraries and deployments)${NC}"
pip install -e ".[dev]"

echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "Your IDE (PyCharm/IntelliJ/VSCode) can now resolve all modules."
echo -e "\nTo activate this environment in your terminal, run:"
echo -e "${BLUE}source venv/bin/activate${NC}"
echo -e "${GREEN}================================================================${NC}"
