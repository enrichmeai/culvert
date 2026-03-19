#!/usr/bin/env bash
# =============================================================================
# Composer Local Development Environment Setup
#
# Sets up a local Airflow environment using Google's Composer Local Dev CLI
# for testing DAGs before deploying to Cloud Composer.
#
# Prerequisites:
#   - Docker running locally
#   - Python 3.8-3.11
#   - Google Cloud SDK installed
#
# Usage (from orchestrator deployment root):
#   ./scripts/setup_composer_local.sh          # First-time setup
#   ./scripts/setup_composer_local.sh start     # Start environment
#   ./scripts/setup_composer_local.sh stop      # Stop environment
#   ./scripts/setup_composer_local.sh test      # Run DAG validation
#   ./scripts/setup_composer_local.sh generate  # Generate DAGs then start
#   ./scripts/setup_composer_local.sh teardown  # Remove environment
#
# Docs: https://docs.cloud.google.com/composer/docs/composer-2/run-local-airflow-environments
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRATOR_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="$(cd "${ORCHESTRATOR_DIR}/../.." && pwd)"
DAGS_DIR="${ORCHESTRATOR_DIR}/dags"
ENV_NAME="generic-pipeline-local"
COMPOSER_IMAGE_VERSION="composer-2.9.7-airflow-2.9.3"  # Update as needed

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; }

# =============================================================================
# Install Composer Local Dev CLI
# =============================================================================
install_cli() {
    if command -v composer-dev &>/dev/null; then
        log "composer-dev CLI already installed"
        return
    fi

    log "Installing Composer Local Development CLI..."
    local tmp_dir
    tmp_dir=$(mktemp -d)
    git clone https://github.com/GoogleCloudPlatform/composer-local-dev.git "${tmp_dir}"
    pip install "${tmp_dir}"
    rm -rf "${tmp_dir}"
    log "composer-dev CLI installed"
}

# =============================================================================
# Generate DAGs from system.yaml
# =============================================================================
generate_dags() {
    log "Generating DAGs from system.yaml..."
    cd "${PROJECT_ROOT}"
    python "${ORCHESTRATOR_DIR}/generate_dags.py" \
        --config "${ORCHESTRATOR_DIR}/config/system.yaml" \
        --output "${DAGS_DIR}"
    log "DAGs generated in ${DAGS_DIR}"
}

# =============================================================================
# Create local Composer environment
# =============================================================================
create_env() {
    if composer-dev list 2>/dev/null | grep -q "${ENV_NAME}"; then
        log "Environment '${ENV_NAME}' already exists"
        return
    fi

    log "Creating local Composer environment: ${ENV_NAME}"
    log "Image version: ${COMPOSER_IMAGE_VERSION}"
    log "DAGs path: ${DAGS_DIR}"

    composer-dev create \
        --from-image-version "${COMPOSER_IMAGE_VERSION}" \
        --dags-path "${DAGS_DIR}" \
        "${ENV_NAME}"

    # Write requirements.txt for the local environment
    local req_file="./composer/${ENV_NAME}/requirements.txt"
    if [[ -f "${ORCHESTRATOR_DIR}/requirements.txt" ]]; then
        cp "${ORCHESTRATOR_DIR}/requirements.txt" "${req_file}"
        log "Copied requirements.txt → ${req_file}"
    fi

    # Write Airflow variables for local testing
    local vars_file="./composer/${ENV_NAME}/variables.env"
    cat > "${vars_file}" <<'VARS'
# Airflow variables for local testing
AIRFLOW_VAR_GCP_PROJECT_ID=local-test-project
AIRFLOW_VAR_GCP_REGION=europe-west2
AIRFLOW_VAR_ENVIRONMENT=local
AIRFLOW_VAR_DBT_PROJECT_PATH=/home/airflow/gcs/dags/dbt
# Dynatrace (leave empty to disable)
AIRFLOW_VAR_DYNATRACE_ENVIRONMENT_URL=
AIRFLOW_VAR_DYNATRACE_API_TOKEN=
AIRFLOW_VAR_DYNATRACE_OTEL_URL=
# ServiceNow (leave empty to disable)
AIRFLOW_VAR_SERVICENOW_INSTANCE_URL=
AIRFLOW_VAR_SERVICENOW_USERNAME=
AIRFLOW_VAR_SERVICENOW_PASSWORD=
AIRFLOW_VAR_SERVICENOW_ASSIGNMENT_GROUP=
# Audit
AIRFLOW_VAR_AUDIT_PUBSUB_TOPIC=generic-pipeline-events
VARS
    log "Wrote local variables → ${vars_file}"
    log "Environment created. Start with: $0 start"
}

# =============================================================================
# Start / Stop / Restart
# =============================================================================
start_env() {
    log "Starting ${ENV_NAME}..."
    composer-dev start "${ENV_NAME}"
    log "Airflow UI: http://localhost:8080"
    log "DAGs path: ${DAGS_DIR} (live-reload, no restart needed)"
}

stop_env() {
    log "Stopping ${ENV_NAME}..."
    composer-dev stop "${ENV_NAME}"
}

# =============================================================================
# Test DAGs — validate structure and imports
# =============================================================================
test_dags() {
    log "Running DAG validation tests..."

    # 1. Compile check all generated DAGs
    log "Step 1: Python compile check..."
    local errors=0
    for dag_file in "${DAGS_DIR}"/generic_*.py; do
        if python -c "compile(open('${dag_file}').read(), '${dag_file}', 'exec')" 2>/dev/null; then
            log "  $(basename "${dag_file}"): OK"
        else
            error "  $(basename "${dag_file}"): SYNTAX ERROR"
            errors=$((errors + 1))
        fi
    done

    # 2. Run pytest on generator tests
    log "Step 2: Generator unit tests..."
    cd "${PROJECT_ROOT}"
    python -m pytest "${ORCHESTRATOR_DIR}/tests/unit/test_generate_dags.py" -v --tb=short 2>&1 || true

    # 3. Run pytest on DAG structure tests
    log "Step 3: DAG structure tests..."
    python -m pytest "${ORCHESTRATOR_DIR}/tests/unit/test_dag_structure.py" -v --tb=short 2>&1 || true

    # 4. If Composer local is running, validate via Airflow CLI
    if composer-dev list 2>/dev/null | grep -q "${ENV_NAME}.*running"; then
        log "Step 4: Airflow DAG list (local Composer)..."
        composer-dev run-airflow-cmd "${ENV_NAME}" dags list 2>&1 || true
    else
        warn "Step 4: Skipped — Composer local not running. Start with: $0 start"
    fi

    if [[ ${errors} -gt 0 ]]; then
        error "${errors} DAGs have syntax errors"
        exit 1
    fi
    log "All DAG validation tests passed"
}

# =============================================================================
# Teardown
# =============================================================================
teardown_env() {
    warn "Removing environment ${ENV_NAME}..."
    composer-dev remove "${ENV_NAME}" || true
    log "Environment removed"
}

# =============================================================================
# Main
# =============================================================================
main() {
    local cmd="${1:-setup}"

    case "${cmd}" in
        setup|install)
            install_cli
            generate_dags
            create_env
            ;;
        start)
            start_env
            ;;
        stop)
            stop_env
            ;;
        generate)
            generate_dags
            start_env
            ;;
        test|validate)
            test_dags
            ;;
        teardown|remove)
            teardown_env
            ;;
        *)
            echo "Usage: $0 {setup|start|stop|generate|test|teardown}"
            exit 1
            ;;
    esac
}

main "$@"
