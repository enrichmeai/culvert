#!/bin/bash
# =============================================================================
# Real End-to-End Pipeline Test
# =============================================================================
# Uploads CSV + .ok trigger files to GCS and waits for the full pipeline to
# execute naturally:
#   GCS upload → Pub/Sub notification → pubsub_trigger_dag
#              → ingestion_dag (Dataflow → ODP)
#              → transformation_dag (dbt → FDP)
#
# Verification is done by polling job_control.pipeline_jobs and checking
# BigQuery row counts. No direct Airflow invocation or BQ inserts.
#
# Usage:
#   ./scripts/gcp/e2e_pipeline_test.sh [--timeout 1200]
#
# Exit codes:
#   0 — all entities completed successfully
#   1 — timeout or one or more entities FAILED
# =============================================================================

set -euo pipefail

# ─── Config ────────────────────────────────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:-joseph-antony-aruja}"
REGION="${REGION:-europe-west2}"
ENV="${ENV:-int}"
SYSTEM_ID="generic"
EXTRACT_DATE=$(date +%Y%m%d)
EXTRACT_DATE_BQ=$(date +%Y-%m-%d)
ENTITIES=(customers accounts decision applications)
TEST_DATA_DIR="deployments/original-data-to-bigqueryload/tests/data"
LANDING_BUCKET="gs://${PROJECT_ID}-${SYSTEM_ID}-${ENV}-landing"
TIMEOUT="${2:-1200}"  # default 20 min
POLL_INTERVAL=30

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; }
info() { echo -e "${YELLOW}ℹ  $*${NC}"; }

bq_count() {
  bq query --use_legacy_sql=false --project_id="$PROJECT_ID" --format=csv \
    --quiet "$1" 2>/dev/null | tail -1 | tr -d ' '
}

# ─── Step 1: Upload files ───────────────────────────────────────────────────
echo ""
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Real E2E Pipeline Test — $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo "  Project : $PROJECT_ID"
echo "  Env     : $ENV"
echo "  Date    : $EXTRACT_DATE"
echo "  Timeout : ${TIMEOUT}s"
echo ""

log "Uploading test files to $LANDING_BUCKET ..."
for entity in "${ENTITIES[@]}"; do
  src="${TEST_DATA_DIR}/generic_${entity}_sample.csv"
  if [[ ! -f "$src" ]]; then
    fail "Test data file not found: $src"
    exit 1
  fi
  dest="${LANDING_BUCKET}/${SYSTEM_ID}/${entity}/generic_${entity}_${EXTRACT_DATE}.csv"
  ok="${LANDING_BUCKET}/${SYSTEM_ID}/${entity}/generic_${entity}_${EXTRACT_DATE}.ok"
  gsutil -q cp "$src" "$dest"
  echo "OK" | gsutil -q cp - "$ok"
  pass "  $entity: CSV + .ok uploaded"
done
echo ""
info "Waiting for Pub/Sub → Airflow trigger chain to fire..."
echo ""

# ─── Step 2: Poll job_control until all entities complete or timeout ─────────
START=$(date +%s)
declare -A STATUS

while true; do
  ELAPSED=$(( $(date +%s) - START ))
  if (( ELAPSED > TIMEOUT )); then
    echo ""
    fail "Timeout after ${TIMEOUT}s — pipeline did not complete in time"
    exit 1
  fi

  ALL_DONE=true
  ANY_FAILED=false

  for entity in "${ENTITIES[@]}"; do
    current="${STATUS[$entity]:-PENDING}"
    # Skip entities already in terminal state
    if [[ "$current" == "COMPLETE" || "$current" == "FAILED" ]]; then
      continue
    fi

    row=$(bq_count "
      SELECT COALESCE(MAX(status), 'NOT_STARTED')
      FROM \`${PROJECT_ID}.job_control.pipeline_jobs\`
      WHERE system_id = 'GENERIC'
        AND entity_name = '${entity}'
        AND DATE(created_at) = '${EXTRACT_DATE_BQ}'
    ")
    STATUS[$entity]="${row:-NOT_STARTED}"
  done

  # Print current status table
  printf "\r  %-15s %-15s %-15s %-15s  [%3ds]" \
    "${STATUS[customers]:-NOT_STARTED}" \
    "${STATUS[accounts]:-NOT_STARTED}" \
    "${STATUS[decision]:-NOT_STARTED}" \
    "${STATUS[applications]:-NOT_STARTED}" \
    "$ELAPSED"

  for entity in "${ENTITIES[@]}"; do
    s="${STATUS[$entity]:-NOT_STARTED}"
    if [[ "$s" != "COMPLETE" ]]; then ALL_DONE=false; fi
    if [[ "$s" == "FAILED" ]];   then ANY_FAILED=true; fi
  done

  if $ANY_FAILED; then
    echo ""
    fail "One or more entities FAILED"
    for entity in "${ENTITIES[@]}"; do
      echo "  $entity: ${STATUS[$entity]:-NOT_STARTED}"
    done
    exit 1
  fi

  if $ALL_DONE; then
    echo ""
    break
  fi

  sleep "$POLL_INTERVAL"
done

pass "All entities completed in $(( $(date +%s) - START ))s"
echo ""

# ─── Step 3: Verify BigQuery row counts ─────────────────────────────────────
log "Verifying BigQuery ODP row counts..."
ERRORS=0
for entity in "${ENTITIES[@]}"; do
  odp_count=$(bq_count "
    SELECT COUNT(*)
    FROM \`${PROJECT_ID}.odp_generic.${entity}\`
    WHERE DATE(_processed_at) = '${EXTRACT_DATE_BQ}'
  ")
  if [[ "$odp_count" -gt 0 ]]; then
    pass "  odp_generic.${entity}: ${odp_count} rows"
  else
    fail "  odp_generic.${entity}: 0 rows — expected data"
    (( ERRORS++ )) || true
  fi
done

echo ""
log "Verifying BigQuery FDP row counts..."
FDP_MODELS=(event_transaction_excess portfolio_account_excess portfolio_account_facility)
for model in "${FDP_MODELS[@]}"; do
  fdp_count=$(bq_count "
    SELECT COUNT(*)
    FROM \`${PROJECT_ID}.fdp_generic.${model}\`
    WHERE _extract_date = '${EXTRACT_DATE_BQ}'
  ")
  if [[ "$fdp_count" -gt 0 ]]; then
    pass "  fdp_generic.${model}: ${fdp_count} rows"
  else
    fail "  fdp_generic.${model}: 0 rows — expected transformed data"
    (( ERRORS++ )) || true
  fi
done

echo ""
if (( ERRORS > 0 )); then
  fail "E2E FAILED — $ERRORS verification(s) failed"
  exit 1
fi

echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ E2E PASSED — full pipeline executed end-to-end${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
echo ""
echo "  Flow:  GCS upload → Pub/Sub → Airflow DAGs → Dataflow → ODP → dbt → FDP"
echo "  Date:  $EXTRACT_DATE_BQ"
echo "  Time:  $(( $(date +%s) - START ))s total"
echo ""
