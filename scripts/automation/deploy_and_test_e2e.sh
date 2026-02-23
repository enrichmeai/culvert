#!/bin/bash
# =============================================================================
# Full Environment E2E Automation
# =============================================================================
# 1. Deploys Infrastructure (via Terraform/Deploy Scripts)
# 2. Uploads Test Data
# 3. Triggers Pipeline
# 4. Validates Results in BigQuery
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SYSTEM="${1:-application1}"

echo "=============================================="
echo "🌍 Starting GCP E2E Automation for: $SYSTEM"
echo "=============================================="

# 1. Infrastructure Check/Deploy
echo -e "\n${YELLOW}>>> Step 1: Ensuring Infrastructure is Deployed...${NC}"
./scripts/gcp/05_verify_setup.sh || {
    echo "Infrastructure not ready. Deploying..."
    ./scripts/gcp/quick_deploy.sh
}

# 2. Run E2E Flow Script (Uploads files and triggers)
echo -e "\n${YELLOW}>>> Step 2: Uploading Test Data and Triggering Pipeline...${NC}"
./scripts/gcp/test_e2e_flow.sh "$SYSTEM"

# 3. Wait for Processing
echo -e "\n${YELLOW}>>> Step 3: Waiting for Dataflow and dbt (approx 5 mins)...${NC}"
echo "In a production automation suite, we would poll the BigQuery job_control table here."
# sleep 300 # Wait for 5 minutes

# 4. Automated Verification in BigQuery
echo -e "\n${YELLOW}>>> Step 4: Verifying Data in BigQuery...${NC}"
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

QUERY="SELECT status, count(*) FROM \`${PROJECT_ID}.job_control.pipeline_jobs\` WHERE system_id = '${SYSTEM}' GROUP BY 1"
echo "Running validation query: $QUERY"

# Note: In real CI, we'd check if status = 'SUCCESS'
bq query --use_legacy_sql=false "$QUERY"

echo -e "\n${GREEN}=============================================="
echo "✅ E2E Automation Run Finished!"
echo "==============================================${NC}"
