#!/bin/bash
# =============================================================================
# Step 3: Create Infrastructure (Buckets, Datasets, Topics)
# =============================================================================
# Usage: ./scripts/gcp/03_create_infrastructure.sh [generic|all]
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"
DEPLOYMENT="${1:-all}"
ENVIRONMENT="${ENVIRONMENT:-dev}"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    exit 1
fi

echo "=============================================="
echo "Step 3: Create Infrastructure"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Deployment: $DEPLOYMENT"
echo "Environment: $ENVIRONMENT"
echo "=============================================="
echo ""

# Helper functions
create_bucket() {
    local name="$1"
    local full="gs://${PROJECT_ID}-${name}"
    if gsutil ls "$full" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} $full"
    else
        echo -n "  Creating: $full... "
        gsutil mb -l "$REGION" -p "$PROJECT_ID" "$full" && echo -e "${GREEN}✅${NC}"
    fi
}

create_dataset() {
    local name="$1"
    if bq show --project_id="$PROJECT_ID" "$name" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} $name"
    else
        echo -n "  Creating: $name... "
        bq mk --project_id="$PROJECT_ID" --location="$REGION" "$name" && echo -e "${GREEN}✅${NC}"
    fi
}

create_topic() {
    local name="$1"
    if gcloud pubsub topics describe "$name" --project="$PROJECT_ID" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} $name"
    else
        echo -n "  Creating topic: $name... "
        gcloud pubsub topics create "$name" --project="$PROJECT_ID" && echo -e "${GREEN}✅${NC}"
    fi
}

create_subscription() {
    local name="$1"
    local topic="$2"
    if gcloud pubsub subscriptions describe "$name" --project="$PROJECT_ID" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} $name"
    else
        echo -n "  Creating subscription: $name... "
        gcloud pubsub subscriptions create "$name" --topic="$topic" --project="$PROJECT_ID" && echo -e "${GREEN}✅${NC}"
    fi
}

create_bq_table() {
    local table="$1"
    local schema="$2"
    local extra_flags="${3:-}"
    if bq show --project_id="$PROJECT_ID" "$table" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} $table"
    else
        echo -n "  Creating: $table... "
        # shellcheck disable=SC2086
        bq mk --project_id="$PROJECT_ID" $extra_flags --table "$table" "$schema" \
            && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⚠️ (check permissions)${NC}"
    fi
}

# Generic Infrastructure
setup_generic() {
    echo -e "${BLUE}=== Generic Infrastructure ===${NC}"
    echo ""
    echo "GCS Buckets:"
    create_bucket "generic-${ENVIRONMENT}-landing"
    create_bucket "generic-${ENVIRONMENT}-archive"
    create_bucket "generic-${ENVIRONMENT}-error"
    create_bucket "generic-${ENVIRONMENT}-temp"

    echo ""
    echo "BigQuery Datasets:"
    create_dataset "odp_generic"
    create_dataset "fdp_generic"
    create_dataset "job_control"

    echo ""
    echo "BigQuery Tables (odp_generic):"
    # Audit columns appended to every ODP table: _run_id, _source_file, _processed_at, _extract_date
    AUDIT="_run_id:STRING,_source_file:STRING,_processed_at:TIMESTAMP,_extract_date:DATE"

    create_bq_table "odp_generic.customers" \
        "customer_id:STRING,first_name:STRING,last_name:STRING,ssn:STRING,dob:DATE,status:STRING,created_date:DATE,${AUDIT}" \
        "--time_partitioning_field created_date --clustering_fields _run_id,status"

    create_bq_table "odp_generic.accounts" \
        "account_id:STRING,customer_id:STRING,account_type:STRING,balance:NUMERIC,status:STRING,open_date:DATE,${AUDIT}" \
        "--time_partitioning_field open_date --clustering_fields _run_id,account_type"

    create_bq_table "odp_generic.decision" \
        "decision_id:STRING,customer_id:STRING,application_id:STRING,decision_code:STRING,decision_date:TIMESTAMP,score:INTEGER,reason_codes:STRING,${AUDIT}" \
        "--clustering_fields _run_id,decision_code"

    create_bq_table "odp_generic.applications" \
        "application_id:STRING,customer_id:STRING,loan_amount:NUMERIC,interest_rate:NUMERIC,term_months:INTEGER,application_date:DATE,status:STRING,event_type:STRING,account_type:STRING,${AUDIT}" \
        "--time_partitioning_field application_date"

    create_bq_table "odp_generic.customers_errors" \
        "customer_id:STRING,raw_record:STRING,error_type:STRING,error_message:STRING,${AUDIT}"

    create_bq_table "odp_generic.accounts_errors" \
        "account_id:STRING,raw_record:STRING,error_type:STRING,error_message:STRING,${AUDIT}"

    create_bq_table "odp_generic.decision_errors" \
        "decision_id:STRING,raw_record:STRING,error_type:STRING,error_message:STRING,${AUDIT}"

    echo ""
    echo "BigQuery Tables (job_control):"
    create_bq_table "job_control.pipeline_jobs" \
        "job_id:STRING,system_id:STRING,entity_name:STRING,run_id:STRING,status:STRING,extract_date:DATE,source_file:STRING,record_count:INTEGER,error_count:INTEGER,started_at:TIMESTAMP,completed_at:TIMESTAMP,error_message:STRING" \
        "--clustering_fields system_id,status"

    echo ""
    echo "Pub/Sub:"
    create_topic "generic-file-notifications"
    create_topic "generic-pipeline-events"
    create_subscription "generic-file-notifications-sub" "generic-file-notifications"
    create_subscription "generic-pipeline-events-sub" "generic-pipeline-events"
    echo ""
}

# Main
case "$DEPLOYMENT" in
    generic|all) setup_generic ;;
    *)   echo "Usage: $0 [generic|all]"; exit 1 ;;
esac

echo -e "${GREEN}✅ Step 3 Complete!${NC}"
echo ""
echo "Next: ./scripts/gcp/04_setup_github_actions.sh"

