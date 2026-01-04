#!/bin/bash
# E2E Test Script for EM Pipeline
# Uploads test files to GCS and creates .ok trigger files

set -e

PROJECT_ID="joseph-antony-aruja"
LANDING_BUCKET="gs://${PROJECT_ID}-em-dev-landing"
EXTRACT_DATE=$(date +%Y%m%d)
TEST_DATA_DIR="deployments/em/tests/data"

echo "=========================================="
echo "EM Pipeline E2E Test"
echo "=========================================="
echo "Project: ${PROJECT_ID}"
echo "Bucket: ${LANDING_BUCKET}"
echo "Extract Date: ${EXTRACT_DATE}"
echo ""

# Function to upload entity file
upload_entity() {
    local entity=$1
    local source_file="${TEST_DATA_DIR}/em_${entity}_sample.csv"
    local dest_path="${LANDING_BUCKET}/em/${entity}/em_${entity}_${EXTRACT_DATE}.csv"
    local ok_path="${LANDING_BUCKET}/em/${entity}/em_${entity}_${EXTRACT_DATE}.ok"

    echo "Uploading ${entity}..."

    # Upload data file
    gsutil cp "${source_file}" "${dest_path}"
    echo "  ✅ Data file: ${dest_path}"

    # Create .ok trigger file
    echo "OK" | gsutil cp - "${ok_path}"
    echo "  ✅ Trigger file: ${ok_path}"
    echo ""
}

# Upload all 3 EM entities
echo "Uploading EM test files..."
echo ""

upload_entity "customers"
upload_entity "accounts"
upload_entity "decision"

echo "=========================================="
echo "✅ All files uploaded successfully!"
echo ""
echo "Expected behavior:"
echo "1. Pub/Sub notifications sent to em-file-notifications topic"
echo "2. em_pubsub_trigger_dag picks up .ok files"
echo "3. em_odp_load_dag loads data to BigQuery"
echo "4. After all 3 entities loaded, em_fdp_transform_dag runs"
echo ""
echo "Monitor at: https://70a37510c4064c61b1a5533f43385267-dot-europe-west2.composer.googleusercontent.com"
echo "=========================================="

