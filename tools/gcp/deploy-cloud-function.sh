#!/bin/bash
# Deploy LOA Auto-Trigger Cloud Function
# This function automatically triggers the pipeline when files are uploaded to GCS

set -e

PROJECT_ID=${1:-"loa-migration-dev"}
BUCKET_NAME="${PROJECT_ID}-loa-data"
FUNCTION_NAME="loa-auto-trigger"
REGION="us-central1"
DATASET="loa_migration"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║        Deploying LOA Auto-Trigger Cloud Function             ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

echo "📋 Configuration:"
echo "  Project:      ${PROJECT_ID}"
echo "  Bucket:       ${BUCKET_NAME}"
echo "  Function:     ${FUNCTION_NAME}"
echo "  Region:       ${REGION}"
echo ""

# Check if Cloud Functions API is enabled
echo "🔧 Checking Cloud Functions API..."
if ! gcloud services list --enabled --project=${PROJECT_ID} --filter="name:cloudfunctions.googleapis.com" --format="value(name)" | grep -q "cloudfunctions"; then
    echo "Enabling Cloud Functions API..."
    gcloud services enable cloudfunctions.googleapis.com --project=${PROJECT_ID}
    echo "✅ API enabled"
else
    echo "✅ API already enabled"
fi

echo ""
echo "📦 Deploying Cloud Function..."
echo ""

cd cloud-functions/loa-auto-trigger

gcloud functions deploy ${FUNCTION_NAME} \
    --gen2 \
    --runtime=python311 \
    --trigger-bucket=${BUCKET_NAME} \
    --entry-point=trigger_pipeline \
    --region=${REGION} \
    --project=${PROJECT_ID} \
    --set-env-vars="GCP_PROJECT=${PROJECT_ID},DATAFLOW_REGION=${REGION},TEMP_LOCATION=gs://${PROJECT_ID}-loa-temp/temp,STAGING_LOCATION=gs://${PROJECT_ID}-loa-temp/staging,OUTPUT_TABLE=${PROJECT_ID}:${DATASET}.applications_raw,ERROR_TABLE=${PROJECT_ID}:${DATASET}.applications_errors" \
    --memory=256MB \
    --timeout=540s \
    --max-instances=10

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              ✅ DEPLOYMENT COMPLETE!                          ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 How to test:"
echo "  1. Upload a CSV file:"
echo "     gsutil cp test.csv gs://${BUCKET_NAME}/input/"
echo ""
echo "  2. Check function logs:"
echo "     gcloud functions logs read ${FUNCTION_NAME} --region=${REGION} --limit=50"
echo ""
echo "  3. View in console:"
echo "     https://console.cloud.google.com/functions/details/${REGION}/${FUNCTION_NAME}?project=${PROJECT_ID}"
echo ""
echo "💰 Cost: ~$0.10-1/month"
echo ""

