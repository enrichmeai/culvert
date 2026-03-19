#!/usr/bin/env bash
# =============================================================================
# Deploy Generated DAGs to Composer + Clear Buckets + Run E2E Tests
#
# Usage:
#   ./scripts/gcp/deploy_dags_and_test.sh                    # Full: deploy + clear + E2E
#   ./scripts/gcp/deploy_dags_and_test.sh --deploy-only       # Just deploy DAGs
#   ./scripts/gcp/deploy_dags_and_test.sh --clear-only        # Just clear buckets + BQ
#   ./scripts/gcp/deploy_dags_and_test.sh --test-only         # Just run E2E tests
#   ./scripts/gcp/deploy_dags_and_test.sh --timeout 1800      # Custom timeout (seconds)
#
# Prerequisites:
#   - gcloud auth configured
#   - Composer environment running
#   - Generated DAGs exist (run generate_dags.py first)
# =============================================================================

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-joseph-antony-aruja}"
ENV="${ENV:-int}"
REGION="${REGION:-europe-west2}"
SYSTEM_ID="generic"
COMPOSER_ENV="generic-${ENV}-composer"
TIMEOUT=1200

# Parse args
DEPLOY=true; CLEAR=true; TEST=true
while [[ $# -gt 0 ]]; do
  case $1 in
    --deploy-only) CLEAR=false; TEST=false; shift ;;
    --clear-only) DEPLOY=false; TEST=false; shift ;;
    --test-only) DEPLOY=false; CLEAR=false; shift ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ORCHESTRATOR_DIR="${PROJECT_ROOT}/deployments/data-pipeline-orchestrator"
DAGS_DIR="${ORCHESTRATOR_DIR}/dags"

echo ""
echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}${BOLD}  Deploy DAGs + Clear + E2E Test${NC}"
echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════${NC}"
echo "  Project   : $PROJECT_ID"
echo "  Env       : $ENV"
echo "  Composer  : $COMPOSER_ENV"
echo "  Deploy    : $DEPLOY"
echo "  Clear     : $CLEAR"
echo "  E2E Test  : $TEST"
echo "  Timeout   : ${TIMEOUT}s"
echo ""

# =============================================================================
# Step 1: Generate DAGs
# =============================================================================
if $DEPLOY; then
  log "Step 1: Generating DAGs from system.yaml..."
  cd "$PROJECT_ROOT"
  python "${ORCHESTRATOR_DIR}/generate_dags.py" \
    --config "${ORCHESTRATOR_DIR}/config/system.yaml" \
    --output "${DAGS_DIR}"

  # Verify generated files exist
  for dag in pubsub_trigger ingestion transformation pipeline_status error_handling; do
    if [[ ! -f "${DAGS_DIR}/${SYSTEM_ID}_${dag}_dag.py" ]]; then
      fail "Missing generated DAG: ${SYSTEM_ID}_${dag}_dag.py"
      exit 1
    fi
  done
  pass "5 DAGs generated"

  # Get Composer DAGs bucket
  log "Step 2: Uploading DAGs to Composer..."
  DAGS_BUCKET=$(gcloud composer environments describe "$COMPOSER_ENV" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format='value(config.dagGcsPrefix)' 2>/dev/null) || true

  if [[ -z "$DAGS_BUCKET" ]]; then
    fail "Cannot find Composer environment: $COMPOSER_ENV"
    exit 1
  fi

  # Clean up stale files
  log "Cleaning up stale library code from DAGs bucket..."
  gsutil -m rm -rf "${DAGS_BUCKET}/generic/gcp_pipeline_*" 2>/dev/null || true
  gsutil -m rm -rf "${DAGS_BUCKET}/generic/__pycache__" 2>/dev/null || true
  # Remove old factory entrypoint if it exists
  gsutil rm "${DAGS_BUCKET}/generic/generic_pipeline.py" 2>/dev/null || true

   # Upload generated DAGs only (config is baked in at generation time)
  gsutil -m cp "${DAGS_DIR}"/*.py "${DAGS_BUCKET}/generic/"
  # Remove any stale config folder (no longer needed)
  gsutil -m rm -r "${DAGS_BUCKET}/generic/config" 2>/dev/null || true

  pass "DAGs deployed to ${DAGS_BUCKET}/generic/"

  # List what's in the bucket
  log "Deployed files:"
  gsutil ls "${DAGS_BUCKET}/generic/" 2>/dev/null | while read -r f; do
    echo "  $(basename "$f")"
  done
fi

# =============================================================================
# Step 2: Clear buckets + BQ data
# =============================================================================
if $CLEAR; then
  log "Step 3: Clearing landing/archive/error buckets..."

  for suffix in landing archive error; do
    bucket="gs://${PROJECT_ID}-${SYSTEM_ID}-${ENV}-${suffix}"
    count=$(gsutil ls "$bucket" 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$count" -gt 0 ]]; then
      gsutil -m rm -r "${bucket}/**" 2>/dev/null || true
      log "  Cleared $bucket ($count objects)"
    else
      log "  $bucket already empty"
    fi
  done

  log "Step 4: Clearing today's job_control and ODP/FDP data..."
  TODAY=$(date +%Y-%m-%d)

  # Clear today's job records
  bq query --use_legacy_sql=false --project_id="$PROJECT_ID" --quiet \
    "DELETE FROM \`${PROJECT_ID}.job_control.pipeline_jobs\` WHERE extract_date = '${TODAY}'" \
    2>/dev/null || warn "Could not clear job_control (table may not exist)"

  # Clear today's ODP data
  for entity in customers accounts decision applications; do
    bq query --use_legacy_sql=false --project_id="$PROJECT_ID" --quiet \
      "DELETE FROM \`${PROJECT_ID}.odp_${SYSTEM_ID}.${entity}\` WHERE _extract_date = '${TODAY}'" \
      2>/dev/null || true
    bq query --use_legacy_sql=false --project_id="$PROJECT_ID" --quiet \
      "DELETE FROM \`${PROJECT_ID}.odp_${SYSTEM_ID}.${entity}_errors\` WHERE _extract_date = '${TODAY}'" \
      2>/dev/null || true
  done

  # Clear today's FDP data
  for model in event_transaction_excess portfolio_account_excess portfolio_account_facility; do
    bq query --use_legacy_sql=false --project_id="$PROJECT_ID" --quiet \
      "DELETE FROM \`${PROJECT_ID}.fdp_${SYSTEM_ID}.${model}\` WHERE _extract_date = '${TODAY}'" \
      2>/dev/null || true
  done

  pass "Buckets and today's data cleared"
fi

# =============================================================================
# Step 3: Run E2E tests
# =============================================================================
if $TEST; then
  log "Step 5: Waiting 60s for Composer to pick up new DAGs..."
  sleep 60

  log "Step 6: Verifying DAGs are visible in Composer..."
  EXPECTED_DAGS=(
    "${SYSTEM_ID}_pubsub_trigger_dag"
    "${SYSTEM_ID}_ingestion_dag"
    "${SYSTEM_ID}_transformation_dag"
    "${SYSTEM_ID}_pipeline_status_dag"
    "${SYSTEM_ID}_error_handling_dag"
  )

  DAG_LIST=$(gcloud composer environments run "$COMPOSER_ENV" \
    --location="$REGION" --project="$PROJECT_ID" \
    dags list 2>/dev/null || echo "")

  for dag in "${EXPECTED_DAGS[@]}"; do
    if echo "$DAG_LIST" | grep -q "$dag"; then
      pass "DAG visible: $dag"
    else
      warn "DAG not yet visible: $dag (may need more time)"
    fi
  done

  log "Step 7: Running E2E pipeline test..."
  "${SCRIPT_DIR}/e2e_pipeline_test.sh" --timeout "$TIMEOUT"
fi

echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  Done!${NC}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════${NC}"
