#!/bin/bash
# =============================================================================
# Bootstrap GCP Infrastructure
# =============================================================================
# This script creates the prerequisite infrastructure needed before
# the main Terraform configurations can run.
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - Terraform installed
#   - GCP Project ID set
#
# Usage:
#   ./bootstrap_infrastructure.sh <PROJECT_ID>
#
# Example:
#   ./bootstrap_infrastructure.sh my-gcp-project-123
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ -z "$1" ]; then
    echo -e "${RED}Error: GCP Project ID required${NC}"
    echo "Usage: $0 <PROJECT_ID>"
    exit 1
fi

PROJECT_ID="$1"
REGION="${2:-europe-west2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOTSTRAP_DIR="$SCRIPT_DIR/../infrastructure/terraform/bootstrap"

echo ""
echo "=============================================="
echo "  GCP Pipeline Infrastructure Bootstrap"
echo "=============================================="
echo ""
echo "Project ID: $PROJECT_ID"
echo "Region:     $REGION"
echo ""

# Check if gcloud is authenticated
echo -e "${YELLOW}Checking gcloud authentication...${NC}"
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null 2>&1; then
    echo -e "${RED}Error: Not authenticated with gcloud${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi
echo -e "${GREEN}✓ gcloud authenticated${NC}"

# Check if terraform is installed
echo -e "${YELLOW}Checking Terraform installation...${NC}"
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform not installed${NC}"
    echo "Install from: https://terraform.io/downloads"
    exit 1
fi
echo -e "${GREEN}✓ Terraform installed ($(terraform version -json | jq -r '.terraform_version'))${NC}"

# Set the project
echo ""
echo -e "${YELLOW}Setting GCP project...${NC}"
gcloud config set project "$PROJECT_ID"
echo -e "${GREEN}✓ Project set to $PROJECT_ID${NC}"

# Check if state bucket already exists
STATE_BUCKET="gcp-pipeline-terraform-state"
echo ""
echo -e "${YELLOW}Checking if Terraform state bucket exists...${NC}"
if gsutil ls -b "gs://$STATE_BUCKET" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ State bucket already exists: $STATE_BUCKET${NC}"
    echo ""
    echo "You can proceed with the main infrastructure deployment:"
    echo "  cd infrastructure/terraform/systems/generic/ingestion"
    echo "  terraform init"
    echo "  terraform apply -var=\"gcp_project_id=$PROJECT_ID\""
    exit 0
fi

# Run bootstrap Terraform
echo ""
echo -e "${YELLOW}Running Terraform bootstrap...${NC}"
cd "$BOOTSTRAP_DIR"

terraform init

terraform apply \
    -var="gcp_project_id=$PROJECT_ID" \
    -var="gcp_region=$REGION" \
    -auto-approve

echo ""
echo "=============================================="
echo -e "${GREEN}  ✓ Bootstrap Complete!${NC}"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Deploy infrastructure manually:"
echo "   cd infrastructure/terraform/systems/generic/ingestion"
echo "   terraform init"
echo "   terraform apply -var=\"gcp_project_id=$PROJECT_ID\""
echo ""
echo "2. Or trigger via GitHub Actions:"
echo "   gh workflow run deploy-generic.yml -f environment=dev -f library_version=1.0.6"
echo ""

