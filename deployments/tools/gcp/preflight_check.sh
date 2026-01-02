#!/bin/bash
###############################################################################
# Pre-Flight Check Script
# Validates environment before running GCP deployment
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                               ║${NC}"
echo -e "${BLUE}║          🔍 LOA GCP DEPLOYMENT - PRE-FLIGHT CHECK 🔍          ║${NC}"
echo -e "${BLUE}║                                                               ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

ERRORS=0
WARNINGS=0

# Check gcloud
echo -n "Checking gcloud CLI... "
if command -v gcloud &> /dev/null; then
    VERSION=$(gcloud --version | head -1 | awk '{print $4}')
    echo -e "${GREEN}✅ Installed (v$VERSION)${NC}"
else
    echo -e "${RED}❌ NOT FOUND${NC}"
    echo "   Install: brew install --cask google-cloud-sdk"
    ((ERRORS++))
fi

# Check bq
echo -n "Checking bq CLI... "
if command -v bq &> /dev/null; then
    echo -e "${GREEN}✅ Installed${NC}"
else
    echo -e "${RED}❌ NOT FOUND${NC}"
    echo "   Install: gcloud components install bq"
    ((ERRORS++))
fi

# Check gsutil
echo -n "Checking gsutil... "
if command -v gsutil &> /dev/null; then
    echo -e "${GREEN}✅ Installed${NC}"
else
    echo -e "${RED}❌ NOT FOUND${NC}"
    echo "   Install: gcloud components install gsutil"
    ((ERRORS++))
fi

# Check Python
echo -n "Checking Python 3... "
if command -v python3 &> /dev/null; then
    VERSION=$(python3 --version | awk '{print $2}')
    MAJOR=$(echo $VERSION | cut -d. -f1)
    MINOR=$(echo $VERSION | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
        echo -e "${GREEN}✅ Installed (v$VERSION)${NC}"
    else
        echo -e "${YELLOW}⚠️  Version $VERSION (need 3.10+)${NC}"
        ((WARNINGS++))
    fi
else
    echo -e "${RED}❌ NOT FOUND${NC}"
    echo "   Install Python 3.10+ from python.org"
    ((ERRORS++))
fi

# Check pip
echo -n "Checking pip... "
if python3 -m pip --version &> /dev/null; then
    echo -e "${GREEN}✅ Installed${NC}"
else
    echo -e "${RED}❌ NOT FOUND${NC}"
    echo "   Install: python3 -m ensurepip"
    ((ERRORS++))
fi

# Check venv
echo -n "Checking virtual environment... "
if [ -d "venv" ]; then
    echo -e "${GREEN}✅ Found (venv/)${NC}"
else
    echo -e "${YELLOW}⚠️  Not found${NC}"
    echo "   Create: python3 -m venv venv"
    ((WARNINGS++))
fi

# Check authentication
echo -n "Checking gcloud auth... "
if gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 &> /dev/null; then
    ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1)
    echo -e "${GREEN}✅ Authenticated ($ACCOUNT)${NC}"
else
    echo -e "${YELLOW}⚠️  Not authenticated${NC}"
    echo "   Login: gcloud auth login"
    ((WARNINGS++))
fi

# Check project files
echo -n "Checking LOA files... "
if [ -f "loa_pipelines/loa_jcl_template.py" ] && \
   [ -f "loa_common/validation.py" ] && \
   [ -f "loa_common/schema.py" ]; then
    echo -e "${GREEN}✅ All files present${NC}"
else
    echo -e "${RED}❌ Missing files${NC}"
    echo "   Ensure you're in the correct directory"
    ((ERRORS++))
fi

# Check deployment scripts
echo -n "Checking deployment scripts... "
if [ -f "deploy_gcp.sh" ] && [ -f "quickstart_gcp.sh" ]; then
    if [ -x "deploy_gcp.sh" ] && [ -x "quickstart_gcp.sh" ]; then
        echo -e "${GREEN}✅ Scripts ready${NC}"
    else
        echo -e "${YELLOW}⚠️  Scripts not executable${NC}"
        echo "   Fix: chmod +x deploy_gcp.sh quickstart_gcp.sh"
        ((WARNINGS++))
    fi
else
    echo -e "${RED}❌ Scripts missing${NC}"
    ((ERRORS++))
fi

# Check Python packages
echo -n "Checking Python packages... "
if python3 -c "import apache_beam, google.cloud.storage, google.cloud.bigquery" 2>/dev/null; then
    echo -e "${GREEN}✅ All packages installed${NC}"
else
    echo -e "${YELLOW}⚠️  Some packages missing${NC}"
    echo "   Install: pip install -r requirements.txt"
    echo "   Install: pip install google-cloud-storage google-cloud-bigquery apache-beam[gcp]"
    ((WARNINGS++))
fi

# Check billing accounts
echo -n "Checking billing accounts... "
if gcloud beta billing accounts list 2>/dev/null | grep -q "ACCOUNT_ID"; then
    COUNT=$(gcloud beta billing accounts list --format="value(name)" 2>/dev/null | wc -l | tr -d ' ')
    echo -e "${GREEN}✅ Found $COUNT billing account(s)${NC}"
else
    echo -e "${YELLOW}⚠️  No billing accounts or can't check${NC}"
    echo "   You'll need to set up billing in GCP Console"
    ((WARNINGS++))
fi

# Check existing deployment
echo -n "Checking existing deployment... "
if [ -f ".env.gcp" ]; then
    echo -e "${GREEN}✅ Found (.env.gcp exists)${NC}"
    source .env.gcp 2>/dev/null || true
    if [ -n "$PROJECT_ID" ]; then
        echo "   Project: $PROJECT_ID"
        echo "   Region: $REGION"
    fi
else
    echo -e "${BLUE}ℹ️  No previous deployment${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}🎉 PRE-FLIGHT CHECK PASSED!${NC}"
    echo ""
    echo "You're ready to deploy! Run:"
    echo ""
    echo -e "  ${YELLOW}./deploy_gcp.sh${NC}"
    echo ""
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  PRE-FLIGHT CHECK PASSED WITH WARNINGS${NC}"
    echo ""
    echo "Issues found: $WARNINGS warning(s)"
    echo "You can proceed, but consider fixing warnings."
    echo ""
    echo "Run:"
    echo ""
    echo -e "  ${YELLOW}./deploy_gcp.sh${NC}"
    echo ""
else
    echo -e "${RED}❌ PRE-FLIGHT CHECK FAILED${NC}"
    echo ""
    echo "Issues found: $ERRORS error(s), $WARNINGS warning(s)"
    echo "Please fix errors before deploying."
    echo ""
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

exit $ERRORS

