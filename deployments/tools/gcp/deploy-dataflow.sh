#!/bin/bash
# LOA Blueprint - Dataflow Pipeline Deployment
# Deploy the Apache Beam pipeline to Google Cloud Dataflow

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}   LOA Blueprint - Dataflow Deployment${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""

# Get project ID
PROJECT_ID=${1:-$(gcloud config get-value project)}

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ No GCP project specified.${NC}"
    echo "Usage: ./scripts/deploy-dataflow.sh [PROJECT_ID]"
    exit 1
fi

REGION="us-central1"
DATASET="loa_migration"
BUCKET_DATA="gs://${PROJECT_ID}-loa-data"
BUCKET_TEMP="gs://${PROJECT_ID}-loa-temp"

echo -e "${YELLOW}📋 Configuration:${NC}"
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Dataset:  ${DATASET}"
echo ""

# Check if pipeline template exists
if [ ! -f "loa_pipelines/loa_jcl_template.py" ]; then
    echo -e "${RED}❌ Pipeline template not found: loa_pipelines/loa_jcl_template.py${NC}"
    exit 1
fi

echo -e "${YELLOW}🚀 Running Dataflow pipeline...${NC}"
echo ""

# Install dependencies
pip install -q -r requirements-ci.txt

# Run the pipeline with DirectRunner (local testing)
python3 -m loa_pipelines.loa_jcl_template \
    --runner=DirectRunner \
    --project=${PROJECT_ID} \
    --region=${REGION} \
    --temp_location=${BUCKET_TEMP}/temp \
    --staging_location=${BUCKET_TEMP}/staging \
    --input_pattern="${BUCKET_DATA}/input/applications_*.csv" \
    --output_table="${PROJECT_ID}:${DATASET}.applications_raw" \
    --error_table="${PROJECT_ID}:${DATASET}.applications_errors" \
    --run_id="manual-$(date +%Y%m%d-%H%M%S)"

echo ""
echo -e "${GREEN}✅ Pipeline execution complete!${NC}"
echo ""
echo -e "${YELLOW}📊 View results in BigQuery:${NC}"
echo "  https://console.cloud.google.com/bigquery?project=${PROJECT_ID}&d=${DATASET}"
echo ""
echo -e "${YELLOW}💡 To run with DataflowRunner (production):${NC}"
echo "  Change --runner=DirectRunner to --runner=DataflowRunner"
echo ""

