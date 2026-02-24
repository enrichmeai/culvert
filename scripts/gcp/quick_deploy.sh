#!/bin/bash
# =============================================================================
# Quick Deploy: Minimal GCP Infrastructure for E2E Testing
# =============================================================================
# Creates only essential resources for testing (no Terraform, no Composer)
# Much faster and cheaper than full deployment.
#
# Usage: ./scripts/gcp/quick_deploy.sh
# Cleanup: ./scripts/gcp/quick_cleanup.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    echo "Run: gcloud config set project <PROJECT_ID>"
    exit 1
fi

echo "=============================================="
echo "Quick Deploy - Minimal GCP Infrastructure"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# Step 1: Enable Required APIs
# -----------------------------------------------------------------------------
echo -e "${BLUE}>>> Step 1: Enable APIs${NC}"

APIS=(
    "storage.googleapis.com"
    "bigquery.googleapis.com"
    "pubsub.googleapis.com"
    "dataflow.googleapis.com"
)

for api in "${APIS[@]}"; do
    echo -n "  Enabling $api... "
    gcloud services enable "$api" --quiet 2>/dev/null && echo "✅" || echo "⚠️ (may already be enabled)"
done

# -----------------------------------------------------------------------------
# Step 2: Create GCS Buckets
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 2: Create GCS Buckets${NC}"

BUCKETS=(
    "${PROJECT_ID}-generic-landing"
    "${PROJECT_ID}-generic-archive"
    "${PROJECT_ID}-generic-error"
    "${PROJECT_ID}-generic-landing"
    "${PROJECT_ID}-generic-archive"
    "${PROJECT_ID}-generic-error"
    "${PROJECT_ID}-dataflow-temp"
)

for bucket in "${BUCKETS[@]}"; do
    if gsutil ls "gs://$bucket" &>/dev/null; then
        echo "  ✅ $bucket (exists)"
    else
        echo -n "  Creating $bucket... "
        gsutil mb -l "$REGION" "gs://$bucket" 2>/dev/null && echo "✅" || echo "❌"
    fi
done

# -----------------------------------------------------------------------------
# Step 3: Create BigQuery Datasets
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 3: Create BigQuery Datasets${NC}"

DATASETS=(
    "odp_generic"
    "fdp_generic"
    "odp_generic"
    "fdp_generic"
    "job_control"
)

for dataset in "${DATASETS[@]}"; do
    if bq show "${PROJECT_ID}:${dataset}" &>/dev/null; then
        echo "  ✅ $dataset (exists)"
    else
        echo -n "  Creating $dataset... "
        bq mk --location="$REGION" --dataset "${PROJECT_ID}:${dataset}" 2>/dev/null && echo "✅" || echo "❌"
    fi
done

# -----------------------------------------------------------------------------
# Step 4: Create BigQuery Tables
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 4: Create BigQuery Tables${NC}"

# Generic Customers table
echo -n "  Creating odp_generic.customers... "
bq mk --table "${PROJECT_ID}:odp_generic.customers" \
    customer_id:STRING,first_name:STRING,last_name:STRING,ssn:STRING,status:STRING,created_date:DATE,_run_id:STRING,_source_file:STRING,_processed_at:TIMESTAMP,_extract_date:DATE \
    2>/dev/null && echo "✅" || echo "⚠️ (may exist)"

# Generic Accounts table
echo -n "  Creating odp_generic.accounts... "
bq mk --table "${PROJECT_ID}:odp_generic.accounts" \
    account_id:STRING,customer_id:STRING,account_type:STRING,balance:NUMERIC,open_date:DATE,_run_id:STRING,_source_file:STRING,_processed_at:TIMESTAMP,_extract_date:DATE \
    2>/dev/null && echo "✅" || echo "⚠️ (may exist)"

# Generic Decision table
echo -n "  Creating odp_generic.decision... "
bq mk --table "${PROJECT_ID}:odp_generic.decision" \
    decision_id:STRING,customer_id:STRING,outcome:STRING,decision_date:DATE,score:INTEGER,_run_id:STRING,_source_file:STRING,_processed_at:TIMESTAMP,_extract_date:DATE \
    2>/dev/null && echo "✅" || echo "⚠️ (may exist)"

# Generic Applications table
echo -n "  Creating odp_generic.applications... "
bq mk --table "${PROJECT_ID}:odp_generic.applications" \
    application_id:STRING,customer_id:STRING,ssn:STRING,loan_amount:NUMERIC,interest_rate:NUMERIC,term_months:INTEGER,application_date:DATE,status:STRING,event_type:STRING,account_type:STRING,_run_id:STRING,_source_file:STRING,_processed_at:TIMESTAMP,_extract_date:DATE \
    2>/dev/null && echo "✅" || echo "⚠️ (may exist)"

# Job Control table
echo -n "  Creating job_control.pipeline_jobs... "
bq mk --table "${PROJECT_ID}:job_control.pipeline_jobs" \
    job_id:STRING,system_id:STRING,entity_name:STRING,run_id:STRING,status:STRING,extract_date:DATE,source_file:STRING,record_count:INTEGER,error_count:INTEGER,started_at:TIMESTAMP,completed_at:TIMESTAMP,error_message:STRING \
    2>/dev/null && echo "✅" || echo "⚠️ (may exist)"

# -----------------------------------------------------------------------------
# Step 5: Create Pub/Sub Topics and Subscriptions
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 5: Create Pub/Sub Topics${NC}"

# Generic Topic
echo -n "  Creating generic-file-notifications... "
gcloud pubsub topics create generic-file-notifications 2>/dev/null && echo "✅" || echo "⚠️ (may exist)"
echo -n "  Creating generic-file-notifications-sub... "
gcloud pubsub subscriptions create generic-file-notifications-sub \
    --topic=generic-file-notifications \
    --ack-deadline=60 2>/dev/null && echo "✅" || echo "⚠️ (may exist)"

# Generic Topic
echo -n "  Creating generic-file-notifications... "
gcloud pubsub topics create generic-file-notifications 2>/dev/null && echo "✅" || echo "⚠️ (may exist)"
echo -n "  Creating generic-file-notifications-sub... "
gcloud pubsub subscriptions create generic-file-notifications-sub \
    --topic=generic-file-notifications \
    --ack-deadline=60 2>/dev/null && echo "✅" || echo "⚠️ (may exist)"

# DLQ Topics
echo -n "  Creating generic-dlq... "
gcloud pubsub topics create generic-dlq 2>/dev/null && echo "✅" || echo "⚠️ (may exist)"
echo -n "  Creating generic-dlq... "
gcloud pubsub topics create generic-dlq 2>/dev/null && echo "✅" || echo "⚠️ (may exist)"

# -----------------------------------------------------------------------------
# Step 6: Setup GCS Notifications (triggers Pub/Sub on .ok file upload)
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}>>> Step 6: Setup GCS Notifications${NC}"

echo -n "  Generic bucket notification... "
gsutil notification create \
    -t "projects/${PROJECT_ID}/topics/generic-file-notifications" \
    -f json \
    -e OBJECT_FINALIZE \
    -p "generic/" \
    "gs://${PROJECT_ID}-generic-landing" 2>/dev/null && echo "✅" || echo "⚠️ (may exist)"

echo -n "  Generic bucket notification... "
gsutil notification create \
    -t "projects/${PROJECT_ID}/topics/generic-file-notifications" \
    -f json \
    -e OBJECT_FINALIZE \
    -p "generic/" \
    "gs://${PROJECT_ID}-generic-landing" 2>/dev/null && echo "✅" || echo "⚠️ (may exist)"

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}=============================================="
echo "Quick Deploy Complete!"
echo "==============================================${NC}"
echo ""
echo "Created resources:"
echo "  📦 GCS Buckets: 7"
echo "  📊 BigQuery Datasets: 5"
echo "  📋 BigQuery Tables: 5"
echo "  📬 Pub/Sub Topics: 4"
echo ""
echo "Next steps:"
echo "  1. Run E2E test: ./scripts/gcp/test_e2e_flow.sh all"
echo "  2. Check costs: https://console.cloud.google.com/billing"
echo ""
echo "To cleanup: ./scripts/gcp/quick_cleanup.sh"
echo ""

