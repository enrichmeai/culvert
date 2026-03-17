#!/bin/bash
# =============================================================================
# Real End-to-End Pipeline Test
# =============================================================================
# Uploads CSV + .ok trigger files to GCS and waits for the full pipeline to
# execute naturally:
#   GCS upload → Pub/Sub → pubsub_trigger_dag
#              → ingestion_dag (Dataflow → ODP → reconcile)
#              → transformation_dag (dbt → FDP → test)
#
# Status is checked at every stage via job_control.pipeline_jobs.
# A timestamped report is written to /tmp/e2e_report_<date>.txt on completion.
#
# Usage:
#   ./scripts/gcp/e2e_pipeline_test.sh [--timeout <seconds>]
#
# Exit codes:
#   0 — all ODP + FDP jobs succeeded and row counts verified
#   1 — any job FAILED, or timeout reached
# =============================================================================

set -euo pipefail

# ─── Config ────────────────────────────────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:-joseph-antony-aruja}"
ENV="${ENV:-int}"
SYSTEM_ID="generic"
EXTRACT_DATE=$(date +%Y%m%d)
EXTRACT_DATE_BQ=$(date +%Y-%m-%d)
ENTITIES=(customers accounts decision applications)
FDP_MODELS=(event_transaction_excess portfolio_account_excess portfolio_account_facility)
TEST_DATA_DIR="deployments/original-data-to-bigqueryload/tests/data"
LANDING_BUCKET="gs://${PROJECT_ID}-${SYSTEM_ID}-${ENV}-landing"
TIMEOUT=1200   # 20 min — Dataflow cold start is ~8 min
POLL_INTERVAL=30
REPORT_FILE="/tmp/e2e_report_${EXTRACT_DATE}_$(date +%H%M%S).txt"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --timeout) TIMEOUT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; }
info() { echo -e "${YELLOW}   $*${NC}"; }
hdr()  { echo -e "\n${BLUE}${BOLD}── $* ──${NC}"; }

# bq_scalar: run a BQ query and return a single scalar value (empty string on error)
bq_scalar() {
  local result
  result=$(bq query --use_legacy_sql=false --project_id="$PROJECT_ID" --format=csv \
    --quiet "$1" 2>/dev/null | tail -1 | tr -d ' \r') || true
  echo "$result"
}

# bq_rows: return a pretty table from BQ query
bq_rows() {
  bq query --use_legacy_sql=false --project_id="$PROJECT_ID" --format=pretty \
    --quiet "$1" 2>/dev/null
}

# Append a line to the report file
report() { echo "$*" >> "$REPORT_FILE"; }

TEST_START=$(date +%s)

# ─── Header ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}${BOLD}  Real E2E Pipeline Test${NC}"
echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════${NC}"
echo "  Project  : $PROJECT_ID"
echo "  Env      : $ENV"
echo "  Date     : $EXTRACT_DATE_BQ"
echo "  Timeout  : ${TIMEOUT}s"
echo "  Report   : $REPORT_FILE"
echo ""

report "E2E Pipeline Test — $EXTRACT_DATE_BQ $(date +%H:%M:%S)"
report "Project: $PROJECT_ID  Env: $ENV"
report "========================================================"

# ─── Checkpoint 1: File Upload ────────────────────────────────────────────────
hdr "Checkpoint 1 — File Upload"
report ""
report "CHECKPOINT 1: File Upload"

UPLOAD_START=$(date +%s)
for entity in "${ENTITIES[@]}"; do
  src="${TEST_DATA_DIR}/generic_${entity}_sample.csv"
  if [[ ! -f "$src" ]]; then
    fail "Test data not found: $src"; exit 1
  fi
  dest="${LANDING_BUCKET}/${SYSTEM_ID}/${entity}/generic_${entity}_${EXTRACT_DATE}.csv"
  ok="${LANDING_BUCKET}/${SYSTEM_ID}/${entity}/generic_${entity}_${EXTRACT_DATE}.ok"
  gsutil -q cp "$src" "$dest"
  echo "OK" | gsutil -q cp - "$ok"
  BYTES=$(wc -c < "$src" | tr -d ' ')
  pass "  $entity — CSV (${BYTES}B) + .ok uploaded"
  report "  UPLOADED: $entity → $dest"
done
UPLOAD_ELAPSED=$(( $(date +%s) - UPLOAD_START ))
pass "All 4 entities uploaded in ${UPLOAD_ELAPSED}s"
report "  All files uploaded in ${UPLOAD_ELAPSED}s"

# ─── Checkpoint 2: Poll ODP Ingestion via job_control ────────────────────────
hdr "Checkpoint 2 — ODP Ingestion  (Pub/Sub → Airflow → Dataflow → BigQuery)"
report ""
report "CHECKPOINT 2: ODP Ingestion"
info "Polling job_control.pipeline_jobs every ${POLL_INTERVAL}s for ODP_INGESTION jobs..."
info "Expected stages: PENDING → RUNNING → SUCCESS"
echo ""

declare -A ODP_STATUS
for e in "${ENTITIES[@]}"; do ODP_STATUS[$e]="NOT_STARTED"; done

POLL_START=$(date +%s)
while true; do
  ELAPSED=$(( $(date +%s) - POLL_START ))
  if (( ELAPSED > TIMEOUT )); then
    echo ""
    fail "Timeout after ${TIMEOUT}s waiting for ODP ingestion"
    report "  TIMEOUT after ${TIMEOUT}s"
    exit 1
  fi

  ALL_DONE=true; ANY_FAILED=false
  for entity in "${ENTITIES[@]}"; do
    [[ "${ODP_STATUS[$entity]}" == "SUCCESS" || "${ODP_STATUS[$entity]}" == "FAILED" ]] && continue
    val=$(bq_scalar "
      SELECT COALESCE(MAX(status), 'NOT_STARTED')
      FROM \`${PROJECT_ID}.job_control.pipeline_jobs\`
      WHERE system_id = 'GENERIC'
        AND entity_type = '${entity}'
        AND job_type = 'ODP_INGESTION'
        AND DATE(created_at) = '${EXTRACT_DATE_BQ}'
    ")
    ODP_STATUS[$entity]="${val:-NOT_STARTED}"
  done

  printf "\r  customers:%-12s accounts:%-12s decision:%-12s applications:%-12s [%3ds]" \
    "${ODP_STATUS[customers]}" "${ODP_STATUS[accounts]}" \
    "${ODP_STATUS[decision]}" "${ODP_STATUS[applications]}" "$ELAPSED"

  for entity in "${ENTITIES[@]}"; do
    [[ "${ODP_STATUS[$entity]}" != "SUCCESS" ]] && ALL_DONE=false
    [[ "${ODP_STATUS[$entity]}" == "FAILED" ]]  && ANY_FAILED=true
  done

  if $ANY_FAILED; then
    echo ""
    fail "One or more ODP ingestion jobs FAILED:"
    for entity in "${ENTITIES[@]}"; do
      [[ "${ODP_STATUS[$entity]}" == "FAILED" ]] && \
        info "  $entity: $(bq_scalar "
          SELECT COALESCE(error_message, failure_stage, 'no detail')
          FROM \`${PROJECT_ID}.job_control.pipeline_jobs\`
          WHERE system_id='GENERIC' AND entity_type='${entity}'
            AND job_type='ODP_INGESTION' AND DATE(created_at)='${EXTRACT_DATE_BQ}'
          ORDER BY created_at DESC LIMIT 1
        ")"
      report "  FAILED: $entity — ${ODP_STATUS[$entity]}"
    done
    exit 1
  fi

  $ALL_DONE && { echo ""; break; }
  sleep "$POLL_INTERVAL"
done

ODP_ELAPSED=$(( $(date +%s) - POLL_START ))
pass "All 4 ODP ingestion jobs SUCCESS in ${ODP_ELAPSED}s"
report "  All ODP jobs SUCCESS in ${ODP_ELAPSED}s"

# ─── Checkpoint 3: ODP Row Counts ─────────────────────────────────────────────
hdr "Checkpoint 3 — ODP Row Counts"
report ""
report "CHECKPOINT 3: ODP Row Counts"

ODP_ERRORS=0
for entity in "${ENTITIES[@]}"; do
  n=$(bq_scalar "
    SELECT COUNT(*) FROM \`${PROJECT_ID}.odp_generic.${entity}\`
    WHERE DATE(_processed_at) = '${EXTRACT_DATE_BQ}'
  ")
  total_records=$(bq_scalar "
    SELECT COALESCE(MAX(total_records), 0)
    FROM \`${PROJECT_ID}.job_control.pipeline_jobs\`
    WHERE system_id='GENERIC' AND entity_type='${entity}'
      AND job_type='ODP_INGESTION' AND DATE(created_at)='${EXTRACT_DATE_BQ}'
  ")
  if [[ "${n:-0}" -gt 0 ]]; then
    pass "  odp_generic.${entity}: ${n} rows (job_control reported: ${total_records})"
    report "  odp_generic.${entity}: ${n} rows"
  else
    fail "  odp_generic.${entity}: 0 rows"
    report "  FAIL odp_generic.${entity}: 0 rows"
    (( ODP_ERRORS++ )) || true
  fi
done

(( ODP_ERRORS > 0 )) && { fail "ODP row count verification failed"; exit 1; }

# ─── Checkpoint 4: Poll FDP Transformation via job_control ───────────────────
hdr "Checkpoint 4 — FDP Transformation  (dbt models)"
report ""
report "CHECKPOINT 4: FDP Transformation"
info "Polling for FDP_TRANSFORMATION jobs..."
echo ""

declare -A FDP_STATUS
for m in "${FDP_MODELS[@]}"; do FDP_STATUS[$m]="NOT_STARTED"; done

POLL_START=$(date +%s)
while true; do
  ELAPSED=$(( $(date +%s) - POLL_START ))
  if (( ELAPSED > TIMEOUT )); then
    echo ""
    fail "Timeout after ${TIMEOUT}s waiting for FDP transformation"
    report "  TIMEOUT after ${TIMEOUT}s"
    exit 1
  fi

  ALL_DONE=true; ANY_FAILED=false
  for model in "${FDP_MODELS[@]}"; do
    [[ "${FDP_STATUS[$model]}" == "SUCCESS" || "${FDP_STATUS[$model]}" == "FAILED" ]] && continue
    val=$(bq_scalar "
      SELECT COALESCE(MAX(status), 'NOT_STARTED')
      FROM \`${PROJECT_ID}.job_control.pipeline_jobs\`
      WHERE system_id = 'GENERIC'
        AND dbt_model_name = '${model}'
        AND job_type = 'FDP_TRANSFORMATION'
        AND DATE(created_at) = '${EXTRACT_DATE_BQ}'
    ")
    FDP_STATUS[$model]="${val:-NOT_STARTED}"
  done

  printf "\r  event_txn:%-12s portfolio_acc:%-12s portfolio_fac:%-12s [%3ds]" \
    "${FDP_STATUS[event_transaction_excess]}" \
    "${FDP_STATUS[portfolio_account_excess]}" \
    "${FDP_STATUS[portfolio_account_facility]}" \
    "$ELAPSED"

  for model in "${FDP_MODELS[@]}"; do
    [[ "${FDP_STATUS[$model]}" != "SUCCESS" ]] && ALL_DONE=false
    [[ "${FDP_STATUS[$model]}" == "FAILED" ]]  && ANY_FAILED=true
  done

  if $ANY_FAILED; then
    echo ""
    fail "One or more FDP transformation jobs FAILED"
    for model in "${FDP_MODELS[@]}"; do
      report "  FAILED: $model — ${FDP_STATUS[$model]}"
    done
    exit 1
  fi

  $ALL_DONE && { echo ""; break; }
  sleep "$POLL_INTERVAL"
done

FDP_ELAPSED=$(( $(date +%s) - POLL_START ))
pass "All 3 FDP transformation jobs SUCCESS in ${FDP_ELAPSED}s"
report "  All FDP jobs SUCCESS in ${FDP_ELAPSED}s"

# ─── Checkpoint 5: FDP Row Counts ─────────────────────────────────────────────
hdr "Checkpoint 5 — FDP Row Counts"
report ""
report "CHECKPOINT 5: FDP Row Counts"

FDP_ERRORS=0
for model in "${FDP_MODELS[@]}"; do
  n=$(bq_scalar "
    SELECT COUNT(*) FROM \`${PROJECT_ID}.fdp_generic.${model}\`
    WHERE _extract_date = '${EXTRACT_DATE_BQ}'
  ")
  if [[ "${n:-0}" -gt 0 ]]; then
    pass "  fdp_generic.${model}: ${n} rows"
    report "  fdp_generic.${model}: ${n} rows"
  else
    fail "  fdp_generic.${model}: 0 rows"
    report "  FAIL fdp_generic.${model}: 0 rows"
    (( FDP_ERRORS++ )) || true
  fi
done

(( FDP_ERRORS > 0 )) && { fail "FDP row count verification failed"; exit 1; }

# ─── Final Summary ────────────────────────────────────────────────────────────
TOTAL_ELAPSED=$(( $(date +%s) - TEST_START ))
echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅ E2E PASSED${NC}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════${NC}"
echo "  Checkpoint 1 — File upload      : ${UPLOAD_ELAPSED}s"
echo "  Checkpoint 2 — ODP ingestion    : ${ODP_ELAPSED}s"
echo "  Checkpoint 3 — ODP row counts   : ✅"
echo "  Checkpoint 4 — FDP transforms   : ${FDP_ELAPSED}s"
echo "  Checkpoint 5 — FDP row counts   : ✅"
echo "  Total time                       : ${TOTAL_ELAPSED}s"
echo ""
echo "  Report saved to: $REPORT_FILE"
echo ""

report ""
report "========================================================"
report "RESULT: PASSED"
report "  Upload:       ${UPLOAD_ELAPSED}s"
report "  ODP ingest:   ${ODP_ELAPSED}s"
report "  FDP transform:${FDP_ELAPSED}s"
report "  Total:        ${TOTAL_ELAPSED}s"
report "Completed: $(date '+%Y-%m-%d %H:%M:%S')"
