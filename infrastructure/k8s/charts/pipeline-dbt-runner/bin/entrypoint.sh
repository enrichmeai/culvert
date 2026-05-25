#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh — pipeline-dbt-runner container entrypoint
#
# Behaviour:
#   1. Validate required environment / mounts.
#   2. Run `dbt deps` if packages.yml exists in the project directory.
#   3. Execute `dbt run` (or any dbt sub-command passed as CMD args).
#
# Environment variables (all have defaults from Dockerfile ENV):
#   DBT_PROJECT       dbt project directory name  (default: bigquery-to-mapped-product)
#   DBT_TARGET        dbt target profile           (default: prod)
#   DBT_PROFILES_DIR  path to profiles.yml         (default: /app/profiles)
#
# GCP auth: relies on Workload Identity / Application Default Credentials
#           injected by GKE — no key files required in the image.
# =============================================================================

set -euo pipefail

# ── Colour helpers (consistent with scripts/airflow-local/up.sh style) ───────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}[$(date +%H:%M:%S)] OK   $*${NC}"; }
fail() { echo -e "${RED}[$(date +%H:%M:%S)] FAIL $*${NC}" >&2; }
info() { echo -e "${YELLOW}[$(date +%H:%M:%S)]      $*${NC}"; }
hdr()  { echo -e "\n${BLUE}── $* ──${NC}"; }

# ── Structured JSON log helper (Cloud Logging compatible) ────────────────────
# Cloud Logging indexes the `message` and `severity` fields automatically.
json_log() {
    local severity="${1:-INFO}"
    local message="${2:-}"
    shift 2 || true
    # Extra key=value pairs become additional JSON fields
    local extras=""
    while [[ $# -gt 0 ]]; do
        local key="${1%%=*}"
        local val="${1#*=}"
        extras="${extras}, \"${key}\": \"${val}\""
        shift
    done
    printf '{"severity":"%s","message":"%s","dbt_project":"%s","dbt_target":"%s","timestamp":"%s"%s}\n' \
        "${severity}" \
        "${message}" \
        "${DBT_PROJECT:-unknown}" \
        "${DBT_TARGET:-unknown}" \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "${extras}"
}

# ── Defaults ─────────────────────────────────────────────────────────────────
DBT_PROJECT="${DBT_PROJECT:-bigquery-to-mapped-product}"
DBT_TARGET="${DBT_TARGET:-prod}"
DBT_PROFILES_DIR="${DBT_PROFILES_DIR:-/app/profiles}"
PROJECT_DIR="/app/projects/${DBT_PROJECT}"

hdr "pipeline-dbt-runner"
log "dbt project  : ${DBT_PROJECT}"
log "dbt target   : ${DBT_TARGET}"
log "profiles dir : ${DBT_PROFILES_DIR}"
log "project dir  : ${PROJECT_DIR}"

# ── Validate mounts ───────────────────────────────────────────────────────────
hdr "Pre-flight checks"

if [[ ! -d "${PROJECT_DIR}" ]]; then
    fail "Project directory not found: ${PROJECT_DIR}"
    fail "Mount your dbt project at /app/projects/${DBT_PROJECT} via a volume."
    json_log "CRITICAL" "dbt project directory not found" "path=${PROJECT_DIR}"
    exit 1
fi
pass "Project directory exists: ${PROJECT_DIR}"

if [[ ! -d "${DBT_PROFILES_DIR}" ]]; then
    fail "Profiles directory not found: ${DBT_PROFILES_DIR}"
    fail "Mount profiles.yml at ${DBT_PROFILES_DIR}/profiles.yml via a volume."
    json_log "CRITICAL" "dbt profiles directory not found" "path=${DBT_PROFILES_DIR}"
    exit 1
fi
pass "Profiles directory exists: ${DBT_PROFILES_DIR}"

# ── GCP / ADC check (non-blocking; WI pods may not have the JSON file) ───────
if command -v gcloud >/dev/null 2>&1; then
    if gcloud auth application-default print-access-token >/dev/null 2>&1; then
        pass "Application Default Credentials available"
        json_log "INFO" "ADC verified"
    else
        info "ADC not yet available via gcloud — relying on Workload Identity metadata server"
        json_log "WARNING" "gcloud ADC check failed; expecting Workload Identity to provide credentials"
    fi
else
    info "gcloud not on PATH — relying on Workload Identity / GOOGLE_APPLICATION_CREDENTIALS"
    json_log "INFO" "gcloud not installed; WI or GOOGLE_APPLICATION_CREDENTIALS expected"
fi

# ── dbt deps ─────────────────────────────────────────────────────────────────
PACKAGES_FILE="${PROJECT_DIR}/packages.yml"
if [[ -f "${PACKAGES_FILE}" ]]; then
    hdr "dbt deps"
    json_log "INFO" "Running dbt deps" "packages_file=${PACKAGES_FILE}"
    log "Found packages.yml — running dbt deps..."
    dbt deps \
        --project-dir "${PROJECT_DIR}" \
        --profiles-dir "${DBT_PROFILES_DIR}" \
        --target "${DBT_TARGET}"
    pass "dbt deps completed"
    json_log "INFO" "dbt deps completed successfully"
else
    info "No packages.yml found at ${PACKAGES_FILE} — skipping dbt deps"
    json_log "INFO" "packages.yml not found; skipping dbt deps"
fi

# ── dbt command ──────────────────────────────────────────────────────────────
# CMD args from Dockerfile default to "run".
# Override via Helm values.command or pod spec args.
DBT_SUBCOMMAND="${1:-run}"
shift || true   # remaining args forwarded to dbt

hdr "dbt ${DBT_SUBCOMMAND}"
json_log "INFO" "Starting dbt ${DBT_SUBCOMMAND}" "subcommand=${DBT_SUBCOMMAND}"
log "Executing: dbt ${DBT_SUBCOMMAND} --project-dir ${PROJECT_DIR} --profiles-dir ${DBT_PROFILES_DIR} --target ${DBT_TARGET} $*"

# shellcheck disable=SC2048 disable=SC2086
dbt "${DBT_SUBCOMMAND}" \
    --project-dir "${PROJECT_DIR}" \
    --profiles-dir "${DBT_PROFILES_DIR}" \
    --target "${DBT_TARGET}" \
    "$@"

EXIT_CODE=$?

if [[ ${EXIT_CODE} -eq 0 ]]; then
    pass "dbt ${DBT_SUBCOMMAND} completed successfully"
    json_log "INFO" "dbt ${DBT_SUBCOMMAND} finished" "exit_code=0"
else
    fail "dbt ${DBT_SUBCOMMAND} exited with code ${EXIT_CODE}"
    json_log "ERROR" "dbt ${DBT_SUBCOMMAND} failed" "exit_code=${EXIT_CODE}"
fi

exit ${EXIT_CODE}
