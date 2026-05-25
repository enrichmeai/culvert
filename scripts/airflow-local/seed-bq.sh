#!/usr/bin/env bash
#
# seed-bq.sh — Create BigQuery datasets in the local emulator.

set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
info() { echo -e "${YELLOW}   $*${NC}"; }

BQ_HOST="${BQ_HOST:-http://localhost:9050}"
BQ_PROJECT="${BQ_PROJECT:-local}"

DATASETS=(odp_generic fdp_generic marts_generic analytics_generic job_control)

log "Creating BigQuery datasets in $BQ_PROJECT at $BQ_HOST"
for ds in "${DATASETS[@]}"; do
  body="{\"datasetReference\":{\"projectId\":\"$BQ_PROJECT\",\"datasetId\":\"$ds\"}}"
  code=$(curl -o /dev/null -s -w "%{http_code}" \
    -X POST -H "Content-Type: application/json" \
    -d "$body" \
    "$BQ_HOST/bigquery/v2/projects/$BQ_PROJECT/datasets")
  case "$code" in
    200|201|409) info "dataset $ds ready" ;;
    *)           info "dataset $ds — HTTP $code (may already exist)" ;;
  esac
done

pass "BigQuery seeded."
