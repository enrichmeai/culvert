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
    create_bucket "generic-${ENVIRONMENT}-segments"

    echo ""
    echo "BigQuery Datasets:"
    create_dataset "odp_generic"
    create_dataset "fdp_generic"
    create_dataset "cdp_generic"
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

    create_bq_table "odp_generic.applications_errors" \
        "application_id:STRING,raw_record:STRING,error_type:STRING,error_message:STRING,${AUDIT}"

    echo ""
    echo "BigQuery Tables (job_control):"
    # pipeline_jobs uses source_files ARRAY — requires JSON schema
    JOBS_SCHEMA_FILE="$(mktemp /tmp/pipeline_jobs_schema_XXXXXX.json)"
    cat > "$JOBS_SCHEMA_FILE" <<'SCHEMA'
[
  {"name": "run_id",           "type": "STRING",    "mode": "REQUIRED"},
  {"name": "system_id",        "type": "STRING",    "mode": "REQUIRED"},
  {"name": "entity_type",      "type": "STRING",    "mode": "REQUIRED"},
  {"name": "extract_date",     "type": "DATE",      "mode": "NULLABLE"},
  {"name": "status",           "type": "STRING",    "mode": "REQUIRED"},
  {"name": "source_files",     "type": "STRING",    "mode": "REPEATED"},
  {"name": "total_records",    "type": "INT64",     "mode": "NULLABLE"},
  {"name": "started_at",       "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "completed_at",     "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "failed_at",        "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "error_code",       "type": "STRING",    "mode": "NULLABLE"},
  {"name": "error_message",    "type": "STRING",    "mode": "NULLABLE"},
  {"name": "failure_stage",    "type": "STRING",    "mode": "NULLABLE"},
  {"name": "error_file_path",  "type": "STRING",    "mode": "NULLABLE"},
  {"name": "created_at",       "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "updated_at",       "type": "TIMESTAMP", "mode": "NULLABLE"}
]
SCHEMA
    if bq show --project_id="$PROJECT_ID" "job_control.pipeline_jobs" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} job_control.pipeline_jobs"
    else
        echo -n "  Creating: job_control.pipeline_jobs... "
        bq mk --project_id="$PROJECT_ID" \
            --clustering_fields system_id,status \
            --table "job_control.pipeline_jobs" "$JOBS_SCHEMA_FILE" \
            && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⚠️ (check permissions)${NC}"
    fi
    rm -f "$JOBS_SCHEMA_FILE"

    # audit_trail: matches AuditRecord from gcp_pipeline_core.audit.records
    create_bq_table "job_control.audit_trail" \
        "run_id:STRING,pipeline_name:STRING,entity_type:STRING,source_file:STRING,record_count:INTEGER,processed_timestamp:TIMESTAMP,processing_duration_seconds:FLOAT,success:BOOLEAN,error_count:INTEGER,audit_hash:STRING" \
        "--time_partitioning_field processed_timestamp --clustering_fields pipeline_name,entity_type"

    echo ""
    echo "BigQuery Tables (cdp_generic):"
    # customer_risk_profile: 3-FDP JOIN — consumed by mainframe-segment-transform
    CDP_SCHEMA_FILE="$(mktemp /tmp/cdp_customer_risk_profile_XXXXXX.json)"
    cat > "$CDP_SCHEMA_FILE" <<'SCHEMA'
[
  {"name": "risk_profile_key",    "type": "STRING",    "mode": "REQUIRED"},
  {"name": "customer_id",         "type": "STRING",    "mode": "REQUIRED"},
  {"name": "first_name",          "type": "STRING",    "mode": "NULLABLE"},
  {"name": "last_name",           "type": "STRING",    "mode": "NULLABLE"},
  {"name": "date_of_birth",       "type": "DATE",      "mode": "NULLABLE"},
  {"name": "ssn_masked",          "type": "STRING",    "mode": "NULLABLE"},
  {"name": "customer_status",     "type": "STRING",    "mode": "NULLABLE"},
  {"name": "account_id",          "type": "STRING",    "mode": "NULLABLE"},
  {"name": "account_type_desc",   "type": "STRING",    "mode": "NULLABLE"},
  {"name": "current_balance",     "type": "NUMERIC",   "mode": "NULLABLE"},
  {"name": "account_open_date",   "type": "DATE",      "mode": "NULLABLE"},
  {"name": "decision_id",         "type": "STRING",    "mode": "NULLABLE"},
  {"name": "decision_code",       "type": "STRING",    "mode": "NULLABLE"},
  {"name": "decision_outcome",    "type": "STRING",    "mode": "NULLABLE"},
  {"name": "decision_date",       "type": "DATE",      "mode": "NULLABLE"},
  {"name": "risk_score",          "type": "INTEGER",   "mode": "NULLABLE"},
  {"name": "decision_reason",     "type": "STRING",    "mode": "NULLABLE"},
  {"name": "application_id",      "type": "STRING",    "mode": "NULLABLE"},
  {"name": "loan_amount",         "type": "NUMERIC",   "mode": "NULLABLE"},
  {"name": "interest_rate",       "type": "NUMERIC",   "mode": "NULLABLE"},
  {"name": "term_months",         "type": "INTEGER",   "mode": "NULLABLE"},
  {"name": "application_date",    "type": "DATE",      "mode": "NULLABLE"},
  {"name": "facility_status",     "type": "STRING",    "mode": "NULLABLE"},
  {"name": "event_type",          "type": "STRING",    "mode": "NULLABLE"},
  {"name": "account_type",        "type": "STRING",    "mode": "NULLABLE"},
  {"name": "cdp_segment",         "type": "STRING",    "mode": "NULLABLE"},
  {"name": "_run_id",             "type": "STRING",    "mode": "NULLABLE"},
  {"name": "_extract_date",       "type": "DATE",      "mode": "NULLABLE"},
  {"name": "_cdp_transformed_ts", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
SCHEMA
    if bq show --project_id="$PROJECT_ID" "cdp_generic.customer_risk_profile" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} cdp_generic.customer_risk_profile"
    else
        echo -n "  Creating: cdp_generic.customer_risk_profile... "
        bq mk --project_id="$PROJECT_ID" \
            --time_partitioning_field _extract_date \
            --clustering_fields customer_id \
            --table "cdp_generic.customer_risk_profile" "$CDP_SCHEMA_FILE" \
            && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⚠️ (check permissions)${NC}"
    fi
    rm -f "$CDP_SCHEMA_FILE"

    echo ""
    echo "Pub/Sub:"
    create_topic "generic-file-notifications"
    create_topic "generic-pipeline-events"
    create_subscription "generic-file-notifications-sub" "generic-file-notifications"
    create_subscription "generic-pipeline-events-sub" "generic-pipeline-events"

    echo ""
    echo "Cloud Composer (Orchestration):"
    COMPOSER_ENV="generic-${ENVIRONMENT}-composer"
    if gcloud composer environments describe "$COMPOSER_ENV" \
        --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        echo -e "  ${YELLOW}Exists:${NC} $COMPOSER_ENV"
    else
        echo -e "  Creating: $COMPOSER_ENV (this takes 15-25 minutes)..."
        gcloud composer environments create "$COMPOSER_ENV" \
            --project="$PROJECT_ID" \
            --location="$REGION" \
            --image-version=composer-2.9.7-airflow-2.9.3 \
            --environment-size=small \
            --service-account="github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
            && echo -e "  ${GREEN}✅ Composer created${NC}" \
            || echo -e "  ${YELLOW}⚠️ Composer creation failed (check permissions/quotas)${NC}"
    fi

    # Set up GCS notification → Pub/Sub for the landing bucket
    echo ""
    echo "GCS Notifications:"
    LANDING_BUCKET="gs://${PROJECT_ID}-generic-${ENVIRONMENT}-landing"
    EXISTING_NOTIFICATIONS=$(gsutil notification list "$LANDING_BUCKET" 2>/dev/null | grep "generic-file-notifications" || true)
    if [ -n "$EXISTING_NOTIFICATIONS" ]; then
        echo -e "  ${YELLOW}Exists:${NC} GCS notification on $LANDING_BUCKET"
    else
        echo -n "  Creating GCS notification → generic-file-notifications... "
        gsutil notification create \
            -t "generic-file-notifications" \
            -f json \
            -e OBJECT_FINALIZE \
            -p "generic/" \
            "$LANDING_BUCKET" \
            && echo -e "${GREEN}✅${NC}" \
            || echo -e "${YELLOW}⚠️ (check permissions)${NC}"
    fi
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

