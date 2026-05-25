#!/usr/bin/env bash
#
# down.sh — Tear down the local Airflow stack and remove volumes.
#
# Usage:
#   ./scripts/airflow-local/down.sh

set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; NC='\033[0m'
log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

log "Stopping containers and removing volumes…"
docker compose down -v

pass "Local Airflow stack stopped. Storage wiped."
