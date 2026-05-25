#!/usr/bin/env bash
#
# up.sh — Start the local Airflow + emulator stack.
#
# Usage:
#   ./scripts/airflow-local/up.sh
#
# After startup:
#   - Airflow UI:         http://localhost:8080  (admin / admin)
#   - Fake GCS:           http://localhost:4443
#   - Pub/Sub emulator:   localhost:8085
#   - BigQuery emulator:  http://localhost:9050
#
# Requires: Docker Desktop or equivalent; `docker compose` plugin.

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; }
info() { echo -e "${YELLOW}   $*${NC}"; }
hdr()  { echo -e "\n${BLUE}── $* ──${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

command -v docker >/dev/null || { fail "docker not found on PATH"; exit 1; }
docker compose version >/dev/null 2>&1 || { fail "docker compose plugin not installed"; exit 1; }

hdr "Starting local Airflow stack"
docker compose up -d

hdr "Waiting for Airflow webserver to be healthy"
for i in $(seq 1 45); do
  if curl -fs http://localhost:8080/health >/dev/null 2>&1; then
    pass "Airflow is up (took ${i}0s or less)"
    break
  fi
  info "still starting… (attempt $i / 45)"
  sleep 2
done

if ! curl -fs http://localhost:8080/health >/dev/null 2>&1; then
  fail "Airflow did not become healthy within 90s. Check: docker compose logs airflow-webserver"
  exit 1
fi

hdr "Stack is ready"
echo ""
info "Airflow UI:         http://localhost:8080  (admin / admin)"
info "Fake GCS:           http://localhost:4443"
info "Pub/Sub emulator:   localhost:8085"
info "BigQuery emulator:  http://localhost:9050"
echo ""
info "Next: ./scripts/airflow-local/seed-all.sh    # seed buckets, topics, datasets"
info "      ./scripts/airflow-local/run-dag.sh ingestion_customers 2026-04-17"
info "      ./scripts/airflow-local/down.sh        # tear it all down"
