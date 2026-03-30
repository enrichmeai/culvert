#!/usr/bin/env bash
# =============================================================================
# Setup CDP Segment Transform Infrastructure (minimal)
# =============================================================================
# Creates the bare minimum to prove the customer segment pipeline:
#   - BigQuery: cdp_generic.customer_risk_profile (partitioned on updated_at)
#   - BigQuery: job_control.pipeline_jobs
#   - BigQuery: job_control.audit_trail
#   - GCS: {project}-generic-{env}-segments (segment output files)
#
# Usage:
#   ./scripts/gcp/setup_cdp_segment_infra.sh [project_id] [env]
# =============================================================================
set -euo pipefail

PROJECT_ID="${1:-joseph-antony-aruja}"
ENV="${2:-int}"
REGION="europe-west2"

echo "============================================"
echo "  CDP Segment — Minimal Infrastructure"
echo "============================================"
echo "Project:  ${PROJECT_ID}"
echo "Env:      ${ENV}"
echo "Region:   ${REGION}"
echo "============================================"
echo ""

# ─── 1. Enable APIs ──────────────────────────────────────────────────────────
echo "=== 1. Enabling APIs ==="
gcloud services enable \
    bigquery.googleapis.com \
    storage.googleapis.com \
    dataflow.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    --project="${PROJECT_ID}" --quiet
echo "  Done."
echo ""

# ─── 2. GCS bucket (segment output) ──────────────────────────────────────────
echo "=== 2. Creating segments bucket ==="
BUCKET="${PROJECT_ID}-generic-${ENV}-segments"
if gsutil ls -b "gs://${BUCKET}" &>/dev/null; then
    echo "  Exists: gs://${BUCKET}"
else
    gsutil mb -p "${PROJECT_ID}" -l "${REGION}" "gs://${BUCKET}"
    echo "  Created: gs://${BUCKET}"
fi
echo ""

# ─── 3. BigQuery datasets ────────────────────────────────────────────────────
echo "=== 3. Creating datasets ==="
for DS in cdp_generic job_control; do
    bq --project_id="${PROJECT_ID}" mk --dataset --force \
        --location="${REGION}" "${PROJECT_ID}:${DS}"
    echo "  ${DS}"
done
echo ""

# ─── 4. CDP table: customer_risk_profile ──────────────────────────────────────
echo "=== 4. Creating cdp_generic.customer_risk_profile ==="
bq --project_id="${PROJECT_ID}" mk --table --force \
    --time_partitioning_field=updated_at \
    --time_partitioning_type=DAY \
    --clustering_fields=customer_id \
    cdp_generic.customer_risk_profile \
    customer_id:STRING,first_name:STRING,last_name:STRING,date_of_birth:DATE,status:STRING,account_count:INTEGER,total_balance:FLOAT,risk_score:INTEGER,risk_category:STRING,updated_at:TIMESTAMP
echo "  Done (partitioned on updated_at, clustered on customer_id)."
echo ""

# ─── 5. Job control tables ───────────────────────────────────────────────────
echo "=== 5. Creating job_control tables ==="

cat > /tmp/pipeline_jobs_schema.json <<'SCHEMA'
[
  {"name": "run_id",         "type": "STRING",    "mode": "REQUIRED"},
  {"name": "system_id",      "type": "STRING",    "mode": "REQUIRED"},
  {"name": "entity_type",    "type": "STRING",    "mode": "REQUIRED"},
  {"name": "extract_date",   "type": "DATE",      "mode": "NULLABLE"},
  {"name": "status",         "type": "STRING",    "mode": "REQUIRED"},
  {"name": "source_files",   "type": "STRING",    "mode": "REPEATED"},
  {"name": "total_records",  "type": "INT64",     "mode": "NULLABLE"},
  {"name": "started_at",     "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "completed_at",   "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "failed_at",      "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "error_code",     "type": "STRING",    "mode": "NULLABLE"},
  {"name": "error_message",  "type": "STRING",    "mode": "NULLABLE"},
  {"name": "failure_stage",  "type": "STRING",    "mode": "NULLABLE"},
  {"name": "error_file_path","type": "STRING",    "mode": "NULLABLE"},
  {"name": "created_at",     "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "updated_at",     "type": "TIMESTAMP", "mode": "NULLABLE"}
]
SCHEMA

bq --project_id="${PROJECT_ID}" mk --table --force \
    --time_partitioning_field=created_at \
    --time_partitioning_type=DAY \
    --clustering_fields=system_id,entity_type,status \
    job_control.pipeline_jobs \
    /tmp/pipeline_jobs_schema.json
echo "  pipeline_jobs"

bq --project_id="${PROJECT_ID}" mk --table --force \
    --time_partitioning_field=processed_timestamp \
    --time_partitioning_type=DAY \
    --clustering_fields=pipeline_name,entity_type \
    job_control.audit_trail \
    run_id:STRING,pipeline_name:STRING,entity_type:STRING,source_file:STRING,record_count:INTEGER,processed_timestamp:TIMESTAMP,processing_duration_seconds:FLOAT,success:BOOLEAN,error_count:INTEGER,audit_hash:STRING
echo "  audit_trail"
echo ""

# ─── Done ─────────────────────────────────────────────────────────────────────
echo "============================================"
echo "  Ready — 3 tables + 1 bucket"
echo "============================================"
echo ""
echo "  cdp_generic.customer_risk_profile"
echo "  job_control.pipeline_jobs"
echo "  job_control.audit_trail"
echo "  gs://${BUCKET}"
echo ""
echo "Next:"
echo "  1. Load test data:"
echo "     deployments/mainframe-segment-transform/scripts/load_cdp_test_data.sh"
echo "  2. Deploy (push to main or manual):"
echo "     gh workflow run deploy-segment-transform.yml"
echo "  3. Tear down:"
echo "     scripts/gcp/teardown_cdp_segment_infra.sh"
echo "============================================"
