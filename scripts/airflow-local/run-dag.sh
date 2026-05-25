#!/usr/bin/env bash
#
# run-dag.sh — Trigger an Airflow DAG inside the local stack and wait for it.
#
# Usage:
#   ./scripts/airflow-local/run-dag.sh <dag_id> [<execution_date>]
#
# Example:
#   ./scripts/airflow-local/run-dag.sh ingestion_customers 2026-04-17

set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; }
info() { echo -e "${YELLOW}   $*${NC}"; }

DAG_ID="${1:-}"
EXEC_DATE="${2:-$(date -u +%Y-%m-%d)}"

if [ -z "$DAG_ID" ]; then
  fail "Usage: $0 <dag_id> [<execution_date>]"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

log "Triggering DAG $DAG_ID for $EXEC_DATE"
docker compose exec -T airflow-scheduler airflow dags trigger "$DAG_ID" -e "${EXEC_DATE}T00:00:00"

log "Waiting for DAG run to finish (timeout: 15 min)"
for i in $(seq 1 90); do
  state=$(docker compose exec -T airflow-scheduler airflow dags list-runs -d "$DAG_ID" --output json 2>/dev/null \
    | python3 -c "import sys,json; runs=json.load(sys.stdin); print(runs[0].get('state','unknown') if runs else 'unknown')" \
    2>/dev/null || echo "unknown")
  case "$state" in
    success) pass "DAG $DAG_ID finished: success"; exit 0 ;;
    failed)  fail "DAG $DAG_ID finished: failed"; exit 1 ;;
    *)       info "state: $state (poll $i / 90)"; sleep 10 ;;
  esac
done

fail "Timed out waiting for $DAG_ID"
exit 1
