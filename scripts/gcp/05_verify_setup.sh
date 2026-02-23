#!/bin/bash
# =============================================================================
# Step 5: Verify Setup
# =============================================================================
# Usage: ./scripts/gcp/05_verify_setup.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    exit 1
fi

echo "=============================================="
echo "Step 5: Verify Setup"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "=============================================="
echo ""

ERRORS=0

# Check services
echo -e "${BLUE}=== Services ===${NC}"
REQUIRED_SERVICES=(
    "bigquery.googleapis.com"
    "storage.googleapis.com"
    "pubsub.googleapis.com"
    "dataflow.googleapis.com"
)

ENABLED=$(gcloud services list --enabled --format="value(config.name)" 2>/dev/null)
for svc in "${REQUIRED_SERVICES[@]}"; do
    if echo "$ENABLED" | grep -q "^${svc}$"; then
        echo -e "  ${GREEN}✅${NC} $svc"
    else
        echo -e "  ${RED}❌${NC} $svc"
        ((ERRORS++))
    fi
done

# Check Terraform state bucket
echo ""
echo -e "${BLUE}=== Terraform State ===${NC}"
if gsutil ls gs://gdw-terraform-state &>/dev/null; then
    echo -e "  ${GREEN}✅${NC} gs://gdw-terraform-state"
else
    echo -e "  ${RED}❌${NC} gs://gdw-terraform-state (missing)"
    ((ERRORS++))
fi

# Check Application1 buckets
echo ""
echo -e "${BLUE}=== Application1 Buckets ===${NC}"
for bucket in application1-landing application1-archive application1-error application1-temp; do
    if gsutil ls "gs://${PROJECT_ID}-${bucket}" &>/dev/null; then
        echo -e "  ${GREEN}✅${NC} gs://${PROJECT_ID}-${bucket}"
    else
        echo -e "  ${RED}❌${NC} gs://${PROJECT_ID}-${bucket}"
        ((ERRORS++))
    fi
done

# Check Application2 buckets
echo ""
echo -e "${BLUE}=== Application2 Buckets ===${NC}"
for bucket in application2-landing application2-archive application2-error application2-temp; do
    if gsutil ls "gs://${PROJECT_ID}-${bucket}" &>/dev/null; then
        echo -e "  ${GREEN}✅${NC} gs://${PROJECT_ID}-${bucket}"
    else
        echo -e "  ${RED}❌${NC} gs://${PROJECT_ID}-${bucket}"
        ((ERRORS++))
    fi
done

# Check BigQuery datasets
echo ""
echo -e "${BLUE}=== BigQuery Datasets ===${NC}"
for ds in odp_application1 fdp_application1 job_control odp_application2 fdp_application2; do
    if bq show --project_id="$PROJECT_ID" "$ds" &>/dev/null; then
        echo -e "  ${GREEN}✅${NC} $ds"
    else
        echo -e "  ${RED}❌${NC} $ds"
        ((ERRORS++))
    fi
done

# Check Pub/Sub topics
echo ""
echo -e "${BLUE}=== Pub/Sub Topics ===${NC}"
for topic in application1-file-notifications application1-pipeline-events application2-file-notifications application2-pipeline-events; do
    if gcloud pubsub topics describe "$topic" --project="$PROJECT_ID" &>/dev/null; then
        echo -e "  ${GREEN}✅${NC} $topic"
    else
        echo -e "  ${RED}❌${NC} $topic"
        ((ERRORS++))
    fi
done

# Check GitHub secrets
echo ""
echo -e "${BLUE}=== GitHub Secrets ===${NC}"
if command -v gh &>/dev/null; then
    SECRETS=$(gh secret list 2>/dev/null || echo "")
    for secret in GCP_SA_KEY GCP_PROJECT_ID; do
        if echo "$SECRETS" | grep -q "$secret"; then
            echo -e "  ${GREEN}✅${NC} $secret"
        else
            echo -e "  ${RED}❌${NC} $secret"
            ((ERRORS++))
        fi
    done
else
    echo -e "  ${YELLOW}⚠️  GitHub CLI not installed, skipping${NC}"
fi

# Summary
echo ""
echo "=============================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Ready to deploy.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Push code to trigger deployment: git push"
    echo "  2. Or manually: gh workflow run deploy-application1.yml"
    echo "  3. Test with: ./scripts/gcp/06_test_pipeline.sh application1"
else
    echo -e "${RED}❌ $ERRORS issue(s) found. Please fix before deploying.${NC}"
fi
echo "=============================================="

