#!/bin/bash
###############################################################################
# Create GCP Service Account for GitHub Actions Deployment
# Usage: ./create-deployment-sa.sh <environment> <project-id>
# Example: ./create-deployment-sa.sh dev loa-migration-dev
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
SA_NAME="loa-github-deployer-${ENV}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="loa-sa-key-${ENV}.json"

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Creating GCP Service Account for GitHub Actions Deployment  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Environment:${NC} ${ENV}"
echo -e "${YELLOW}Project ID:${NC} ${PROJECT_ID}"
echo -e "${YELLOW}Service Account:${NC} ${SA_EMAIL}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Install from: https://cloud.google.com/sdk/install${NC}"
    exit 1
fi

# Set project
echo -e "${BLUE}Setting project...${NC}"
gcloud config set project ${PROJECT_ID}

# Check if service account already exists
if gcloud iam service-accounts describe ${SA_EMAIL} --project=${PROJECT_ID} &> /dev/null; then
    echo -e "${YELLOW}⚠️  Service account already exists: ${SA_EMAIL}${NC}"
    read -p "Delete and recreate? (y/n): " RECREATE
    if [[ $RECREATE =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Deleting existing service account...${NC}"
        gcloud iam service-accounts delete ${SA_EMAIL} --project=${PROJECT_ID} --quiet
    else
        echo -e "${YELLOW}Using existing service account${NC}"
    fi
fi

# Create service account
if ! gcloud iam service-accounts describe ${SA_EMAIL} --project=${PROJECT_ID} &> /dev/null; then
    echo -e "${BLUE}Creating service account...${NC}"
    gcloud iam service-accounts create ${SA_NAME} \
        --display-name="LOA GitHub Deployer (${ENV})" \
        --description="Service account for deploying LOA pipeline from GitHub Actions" \
        --project=${PROJECT_ID}
    echo -e "${GREEN}✅ Service account created${NC}"
else
    echo -e "${GREEN}✅ Using existing service account${NC}"
fi

# Grant IAM roles
echo ""
echo -e "${BLUE}Granting IAM roles...${NC}"

ROLES=(
    "roles/dataflow.admin"
    "roles/bigquery.admin"
    "roles/storage.admin"
    "roles/iam.serviceAccountUser"
    "roles/logging.logWriter"
    "roles/monitoring.metricWriter"
)

for role in "${ROLES[@]}"; do
    echo -e "${BLUE}  Granting ${role}...${NC}"
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="${role}" \
        --condition=None \
        --quiet > /dev/null 2>&1 || echo -e "${YELLOW}  ⚠️  Role may already be granted${NC}"
done

echo -e "${GREEN}✅ IAM roles granted${NC}"

# Create key
echo ""
echo -e "${BLUE}Creating service account key...${NC}"

if [ -f "${KEY_FILE}" ]; then
    echo -e "${YELLOW}⚠️  Key file already exists: ${KEY_FILE}${NC}"
    read -p "Overwrite? (y/n): " OVERWRITE
    if [[ $OVERWRITE =~ ^[Yy]$ ]]; then
        rm "${KEY_FILE}"
    else
        KEY_FILE="loa-sa-key-${ENV}-$(date +%Y%m%d-%H%M%S).json"
        echo -e "${YELLOW}Using new filename: ${KEY_FILE}${NC}"
    fi
fi

gcloud iam service-accounts keys create ${KEY_FILE} \
    --iam-account=${SA_EMAIL} \
    --project=${PROJECT_ID}

echo -e "${GREEN}✅ Key created: ${KEY_FILE}${NC}"

# Create bucket if needed
echo ""
read -p "Create Cloud Storage bucket for Dataflow? (y/n): " CREATE_BUCKET
if [[ $CREATE_BUCKET =~ ^[Yy]$ ]]; then
    BUCKET_NAME="loa-dataflow-${ENV}-${PROJECT_ID}"
    REGION="us-central1"

    echo -e "${BLUE}Creating bucket: gs://${BUCKET_NAME}/${NC}"
    gsutil mb -p ${PROJECT_ID} -c STANDARD -l ${REGION} gs://${BUCKET_NAME}/ 2>&1 | grep -v "already exists" || echo -e "${YELLOW}  Bucket already exists${NC}"

    # Set lifecycle policy
    cat > /tmp/lifecycle.json << 'EOF'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 7}
      }
    ]
  }
}
EOF
    gsutil lifecycle set /tmp/lifecycle.json gs://${BUCKET_NAME}/
    rm /tmp/lifecycle.json

    echo -e "${GREEN}✅ Bucket created: gs://${BUCKET_NAME}/${NC}"
else
    BUCKET_NAME="<your-bucket-name>"
fi

# Summary
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Service Account Setup Complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Service Account Details:${NC}"
echo "  Email: ${SA_EMAIL}"
echo "  Key File: ${KEY_FILE}"
echo ""
echo -e "${YELLOW}IAM Roles Granted:${NC}"
for role in "${ROLES[@]}"; do
    echo "  ✓ ${role}"
done
echo ""

# GitHub secrets instructions
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Next Steps: Add GitHub Secrets${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Using GitHub CLI (recommended):${NC}"
echo ""
echo "  # Add service account key"
echo "  gh secret set GCP_SA_KEY_${ENV^^} < ${KEY_FILE}"
echo ""
echo "  # Add project ID"
echo "  gh secret set GCP_PROJECT_ID_${ENV^^} --body \"${PROJECT_ID}\""
echo ""
echo "  # Add bucket name"
echo "  gh secret set GCS_BUCKET_${ENV^^} --body \"${BUCKET_NAME}\""
echo ""
echo -e "${BLUE}Using GitHub Web UI:${NC}"
echo ""
echo "  1. Go to: https://github.com/YOUR_ORG/YOUR_REPO/settings/secrets/actions"
echo "  2. Click 'New repository secret'"
echo "  3. Add these secrets:"
echo ""
echo -e "     ${YELLOW}Name:${NC} GCP_SA_KEY_${ENV^^}"
echo "     Value: (paste entire contents of ${KEY_FILE})"
echo ""
echo -e "     ${YELLOW}Name:${NC} GCP_PROJECT_ID_${ENV^^}"
echo "     Value: ${PROJECT_ID}"
echo ""
echo -e "     ${YELLOW}Name:${NC} GCS_BUCKET_${ENV^^}"
echo "     Value: ${BUCKET_NAME}"
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${RED}⚠️  SECURITY REMINDER:${NC}"
echo "  • Keep ${KEY_FILE} secure and never commit to Git"
echo "  • Delete local copy after uploading to GitHub"
echo "  • Rotate keys every 90 days"
echo ""
echo -e "${BLUE}To delete local key file:${NC}"
echo "  shred -u ${KEY_FILE}  # Linux/Mac"
echo "  rm ${KEY_FILE}  # After uploading to GitHub"
echo ""
echo -e "${GREEN}✅ Setup complete for ${ENV} environment!${NC}"
echo ""

# Automatically add secrets via gh CLI
if command -v gh &> /dev/null; then
    echo ""
    echo -e "${BLUE}Checking GitHub CLI authentication...${NC}"

    # Check if gh is authenticated
    if gh auth status &> /dev/null; then
        echo -e "${GREEN}✅ GitHub CLI authenticated${NC}"

        read -p "Add secrets to GitHub now? (y/n): " ADD_SECRETS
        if [[ $ADD_SECRETS =~ ^[Yy]$ ]]; then
            echo ""
            echo -e "${BLUE}Adding secrets to GitHub...${NC}"

            # Add service account key
            gh secret set GCP_SA_KEY_${ENV^^} < ${KEY_FILE}
            echo -e "${GREEN}✅ Added GCP_SA_KEY_${ENV^^}${NC}"

            # Add project ID
            gh secret set GCP_PROJECT_ID_${ENV^^} --body "${PROJECT_ID}"
            echo -e "${GREEN}✅ Added GCP_PROJECT_ID_${ENV^^}${NC}"

            # Add bucket name
            gh secret set GCS_BUCKET_${ENV^^} --body "${BUCKET_NAME}"
            echo -e "${GREEN}✅ Added GCS_BUCKET_${ENV^^}${NC}"

            echo ""
            echo -e "${GREEN}✅ All secrets added to GitHub!${NC}"
            echo ""

            # Verify secrets were added
            echo -e "${BLUE}Verifying secrets...${NC}"
            gh secret list | grep -E "GCP_SA_KEY_${ENV^^}|GCP_PROJECT_ID_${ENV^^}|GCS_BUCKET_${ENV^^}"
            echo ""

            # Offer to delete local key
            read -p "Delete local key file ${KEY_FILE} for security? (y/n): " DELETE_KEY
            if [[ $DELETE_KEY =~ ^[Yy]$ ]]; then
                shred -u ${KEY_FILE} 2>/dev/null || rm ${KEY_FILE}
                echo -e "${GREEN}✅ Key file securely deleted${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}⚠️  GitHub CLI not authenticated${NC}"
        echo ""
        echo -e "${BLUE}To authenticate, run:${NC}"
        echo "  gh auth login"
        echo ""
        echo -e "${YELLOW}After authentication, you can manually add secrets:${NC}"
        echo "  gh secret set GCP_SA_KEY_${ENV^^} < ${KEY_FILE}"
        echo "  gh secret set GCP_PROJECT_ID_${ENV^^} --body \"${PROJECT_ID}\""
        echo "  gh secret set GCS_BUCKET_${ENV^^} --body \"${BUCKET_NAME}\""
    fi
else
    echo ""
    echo -e "${YELLOW}⚠️  GitHub CLI (gh) not found${NC}"
    echo ""
    echo -e "${BLUE}To install GitHub CLI:${NC}"
    echo "  brew install gh"
    echo ""
    echo -e "${BLUE}Then authenticate:${NC}"
    echo "  gh auth login"
    echo ""
    echo -e "${BLUE}Then add secrets:${NC}"
    echo "  gh secret set GCP_SA_KEY_${ENV^^} < ${KEY_FILE}"
    echo "  gh secret set GCP_PROJECT_ID_${ENV^^} --body \"${PROJECT_ID}\""
    echo "  gh secret set GCS_BUCKET_${ENV^^} --body \"${BUCKET_NAME}\""
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
w
