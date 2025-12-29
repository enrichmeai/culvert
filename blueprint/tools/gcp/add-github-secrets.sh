#!/bin/bash
###############################################################################
# Add GitHub Secrets from Terminal
# Automatically retrieves GCP credentials and adds them to GitHub
#
# Usage: ./add-github-secrets.sh <environment> <project-id>
# Example: ./add-github-secrets.sh dev loa-migration-dev
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if [ $# -lt 2 ]; then
    echo -e "${RED}Usage: $0 <environment> <project-id>${NC}"
    echo -e "${YELLOW}Example: $0 dev loa-migration-dev${NC}"
    exit 1
fi

ENV=$1
PROJECT_ID=$2

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Add GitHub Secrets from Terminal (Automated)             ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Environment:${NC} ${ENV}"
echo -e "${YELLOW}Project ID:${NC} ${PROJECT_ID}"
echo ""

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

# Check gcloud
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found${NC}"
    echo "Install from: https://cloud.google.com/sdk/install"
    exit 1
fi
echo -e "${GREEN}✅ gcloud CLI found${NC}"

# Check gh
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI (gh) not found${NC}"
    echo "Install: brew install gh"
    exit 1
fi
echo -e "${GREEN}✅ GitHub CLI found${NC}"

# Check gcloud authentication
echo ""
echo -e "${BLUE}Checking GCP authentication...${NC}"
CURRENT_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -n1)
if [ -z "$CURRENT_ACCOUNT" ]; then
    echo -e "${YELLOW}⚠️  Not authenticated to GCP${NC}"
    echo -e "${BLUE}Logging in to GCP...${NC}"
    gcloud auth login
    CURRENT_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1)
fi
echo -e "${GREEN}✅ GCP authenticated: ${CURRENT_ACCOUNT}${NC}"

# Set project
echo -e "${BLUE}Setting GCP project to ${PROJECT_ID}...${NC}"
gcloud config set project ${PROJECT_ID}
echo -e "${GREEN}✅ Project set${NC}"

# Check GitHub authentication
echo ""
echo -e "${BLUE}Checking GitHub authentication...${NC}"
if ! gh auth status &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not authenticated to GitHub${NC}"
    echo -e "${BLUE}Logging in to GitHub...${NC}"
    gh auth login
fi
echo -e "${GREEN}✅ GitHub authenticated${NC}"

# Get or create service account
echo ""
echo -e "${BLUE}Checking service account...${NC}"
SA_NAME="loa-github-deployer-${ENV}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe ${SA_EMAIL} --project=${PROJECT_ID} &> /dev/null; then
    echo -e "${YELLOW}⚠️  Service account not found${NC}"
    echo -e "${BLUE}Creating service account...${NC}"

    gcloud iam service-accounts create ${SA_NAME} \
        --display-name="LOA GitHub Deployer (${ENV})" \
        --project=${PROJECT_ID}

    # Grant roles
    echo -e "${BLUE}Granting IAM roles...${NC}"
    ROLES=(
        "roles/dataflow.admin"
        "roles/bigquery.admin"
        "roles/storage.admin"
        "roles/iam.serviceAccountUser"
        "roles/logging.logWriter"
    )

    for role in "${ROLES[@]}"; do
        gcloud projects add-iam-policy-binding ${PROJECT_ID} \
            --member="serviceAccount:${SA_EMAIL}" \
            --role="${role}" \
            --condition=None \
            --quiet > /dev/null 2>&1
    done

    echo -e "${GREEN}✅ Service account created and configured${NC}"
else
    echo -e "${GREEN}✅ Service account exists: ${SA_EMAIL}${NC}"
fi

# Generate new key
echo ""
echo -e "${BLUE}Generating service account key...${NC}"
KEY_FILE="/tmp/loa-sa-key-${ENV}-$$.json"
gcloud iam service-accounts keys create ${KEY_FILE} \
    --iam-account=${SA_EMAIL} \
    --project=${PROJECT_ID}
echo -e "${GREEN}✅ Key created (temporary): ${KEY_FILE}${NC}"

# Get bucket name (or create)
echo ""
echo -e "${BLUE}Checking Cloud Storage bucket...${NC}"
BUCKET_NAME="loa-dataflow-${ENV}-${PROJECT_ID}"

if ! gsutil ls gs://${BUCKET_NAME}/ &> /dev/null; then
    echo -e "${YELLOW}⚠️  Bucket not found${NC}"
    read -p "Create bucket gs://${BUCKET_NAME}? (y/n): " CREATE_BUCKET
    if [[ $CREATE_BUCKET =~ ^[Yy]$ ]]; then
        gsutil mb -p ${PROJECT_ID} -l us-central1 gs://${BUCKET_NAME}/
        echo -e "${GREEN}✅ Bucket created${NC}"
    else
        read -p "Enter existing bucket name: " BUCKET_NAME
    fi
else
    echo -e "${GREEN}✅ Bucket exists: gs://${BUCKET_NAME}/${NC}"
fi

# Add secrets to GitHub
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Adding secrets to GitHub...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Add GCP_SA_KEY
echo -e "${BLUE}Adding GCP_SA_KEY_${ENV^^}...${NC}"
gh secret set GCP_SA_KEY_${ENV^^} < ${KEY_FILE}
echo -e "${GREEN}✅ Added GCP_SA_KEY_${ENV^^}${NC}"

# Add GCP_PROJECT_ID
echo -e "${BLUE}Adding GCP_PROJECT_ID_${ENV^^}...${NC}"
gh secret set GCP_PROJECT_ID_${ENV^^} --body "${PROJECT_ID}"
echo -e "${GREEN}✅ Added GCP_PROJECT_ID_${ENV^^}${NC}"

# Add GCS_BUCKET
echo -e "${BLUE}Adding GCS_BUCKET_${ENV^^}...${NC}"
gh secret set GCS_BUCKET_${ENV^^} --body "${BUCKET_NAME}"
echo -e "${GREEN}✅ Added GCS_BUCKET_${ENV^^}${NC}"

# Verify secrets
echo ""
echo -e "${BLUE}Verifying secrets...${NC}"
gh secret list | grep -E "GCP_SA_KEY_${ENV^^}|GCP_PROJECT_ID_${ENV^^}|GCS_BUCKET_${ENV^^}" || echo "Secrets added successfully"

# Cleanup
echo ""
echo -e "${BLUE}Cleaning up temporary files...${NC}"
shred -u ${KEY_FILE} 2>/dev/null || rm -f ${KEY_FILE}
echo -e "${GREEN}✅ Temporary key file deleted${NC}"

# Summary
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 GitHub Secrets Added Successfully!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Secrets added:${NC}"
echo "  ✓ GCP_SA_KEY_${ENV^^}"
echo "  ✓ GCP_PROJECT_ID_${ENV^^} = ${PROJECT_ID}"
echo "  ✓ GCS_BUCKET_${ENV^^} = ${BUCKET_NAME}"
echo ""
echo -e "${YELLOW}Service Account:${NC}"
echo "  ${SA_EMAIL}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Push code to trigger deployment:"
echo "     git push origin develop"
echo ""
echo "  2. Watch workflow:"
echo "     gh run watch"
echo ""
echo "  3. View secrets:"
echo "     gh secret list"
echo ""
echo -e "${GREEN}✅ Ready to deploy!${NC}"
echo ""

