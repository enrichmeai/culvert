#!/bin/bash
# =============================================================================
# Step 4: Setup GitHub Actions for GCP Deployment
# =============================================================================
# Creates service account and outputs key for GitHub secrets
# Usage: ./scripts/gcp/04_setup_github_actions.sh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
SA_NAME="github-actions-deploy"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    exit 1
fi

echo "=============================================="
echo "Setup GitHub Actions for GCP Deployment"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Service Account: $SA_EMAIL"
echo "=============================================="
echo ""

# Create service account
echo -n "Creating service account... "
if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
    echo -e "${YELLOW}Already exists${NC}"
else
    gcloud iam service-accounts create "$SA_NAME" \
        --project="$PROJECT_ID" \
        --display-name="GitHub Actions Deploy" \
        --description="Service account for GitHub Actions CI/CD" && echo -e "${GREEN}✅${NC}"
fi

# Grant roles
echo ""
echo "Granting IAM roles..."

ROLES=(
    "roles/bigquery.admin"
    "roles/storage.admin"
    "roles/pubsub.admin"
    "roles/dataflow.admin"
    "roles/iam.serviceAccountUser"
    "roles/iam.serviceAccountAdmin"
    "roles/logging.admin"
    "roles/monitoring.admin"
    "roles/cloudbuild.builds.builder"
)

for role in "${ROLES[@]}"; do
    echo -n "  $role... "
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$role" \
        --quiet &>/dev/null && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}(may already exist)${NC}"
done

# Create and download key
echo ""
echo "Creating service account key..."
KEY_FILE="/tmp/gcp-sa-key.json"
gcloud iam service-accounts keys create "$KEY_FILE" \
    --iam-account="$SA_EMAIL" \
    --project="$PROJECT_ID"

echo ""
echo -e "${GREEN}=============================================="
echo "Service account created successfully!"
echo "==============================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Add secrets to GitHub repository:"
echo ""
echo "   gh secret set GCP_SA_KEY < $KEY_FILE"
echo "   gh secret set GCP_PROJECT_ID --body '$PROJECT_ID'"
echo ""
echo "2. Or manually add via GitHub UI:"
echo "   - Go to: Settings > Secrets and variables > Actions"
echo "   - Add secret: GCP_SA_KEY (paste contents of $KEY_FILE)"
echo "   - Add secret: GCP_PROJECT_ID = $PROJECT_ID"
echo ""
echo "3. Verify secrets are set:"
echo "   gh secret list"
echo ""
echo -e "${YELLOW}IMPORTANT: Delete the key file after adding to GitHub:${NC}"
echo "   rm $KEY_FILE"

