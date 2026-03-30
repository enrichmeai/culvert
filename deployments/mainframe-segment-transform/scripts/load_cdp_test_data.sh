#!/usr/bin/env bash
# =============================================================================
# Load CDP Test Data into BigQuery
# =============================================================================
# Loads sample JSON data directly into CDP BigQuery tables for testing
# the mainframe segment transform pipeline without running the full
# ODP → FDP → CDP pipeline.
#
# Usage:
#   ./scripts/load_cdp_test_data.sh [project_id] [dataset]
#
# Example:
#   ./scripts/load_cdp_test_data.sh joseph-antony-aruja cdp_generic
# =============================================================================
set -euo pipefail

PROJECT_ID="${1:-joseph-antony-aruja}"
CDP_DATASET="${2:-cdp_generic}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/../tests/data"

echo "============================================"
echo "  CDP Test Data Loader"
echo "============================================"
echo "Project:  ${PROJECT_ID}"
echo "Dataset:  ${CDP_DATASET}"
echo "Data dir: ${DATA_DIR}"
echo "============================================"

# Ensure dataset exists
echo ""
echo "--- Creating dataset ${CDP_DATASET} (if not exists) ---"
bq --project_id="${PROJECT_ID}" mk --dataset --if_not_exists \
    --location=europe-west2 \
    "${PROJECT_ID}:${CDP_DATASET}"

# Table schemas (inline for simplicity — matches the SQL queries in templates)
declare -A TABLE_SCHEMAS
TABLE_SCHEMAS[customer_risk_profile]="customer_id:STRING,first_name:STRING,last_name:STRING,date_of_birth:DATE,status:STRING,account_count:INTEGER,total_balance:FLOAT,risk_score:INTEGER,risk_category:STRING,updated_at:TIMESTAMP"

# Map table names to JSON test data files
declare -A TABLE_FILES
TABLE_FILES[customer_risk_profile]="cdp_customer_risk_profile.json"

LOAD_COUNT=0
FAIL_COUNT=0

for TABLE in customer_risk_profile; do
    FILE="${DATA_DIR}/${TABLE_FILES[$TABLE]}"
    SCHEMA="${TABLE_SCHEMAS[$TABLE]}"
    FULL_TABLE="${PROJECT_ID}:${CDP_DATASET}.${TABLE}"

    echo ""
    echo "--- Loading ${TABLE} ---"

    if [ ! -f "${FILE}" ]; then
        echo "  ERROR: Data file not found: ${FILE}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        continue
    fi

    ROWS=$(python3 -c "import json; print(len(json.load(open('${FILE}'))))")
    echo "  Source: ${FILE} (${ROWS} rows)"
    echo "  Target: ${FULL_TABLE}"

    # Load with --replace to ensure clean state
    if bq --project_id="${PROJECT_ID}" load \
        --source_format=NEWLINE_DELIMITED_JSON \
        --replace \
        "${CDP_DATASET}.${TABLE}" \
        "${FILE}" \
        "${SCHEMA}" 2>&1; then
        echo "  OK: Loaded ${ROWS} rows into ${TABLE}"
        LOAD_COUNT=$((LOAD_COUNT + 1))
    else
        echo "  FAIL: Could not load ${TABLE}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

echo ""
echo "============================================"
echo "  Summary"
echo "============================================"
echo "Tables loaded:  ${LOAD_COUNT}/1"
echo "Tables failed:  ${FAIL_COUNT}/1"
echo ""

# Verify row counts
echo "--- Verification ---"
for TABLE in customer_risk_profile; do
    COUNT=$(bq --project_id="${PROJECT_ID}" query --nouse_legacy_sql --format=csv \
        "SELECT COUNT(*) AS cnt FROM \`${PROJECT_ID}.${CDP_DATASET}.${TABLE}\`" 2>/dev/null | tail -1)
    echo "  ${CDP_DATASET}.${TABLE}: ${COUNT} rows"
done

echo ""
if [ "${FAIL_COUNT}" -eq 0 ]; then
    echo "CDP test data loaded successfully. Ready for segment transform E2E test."
    exit 0
else
    echo "Some tables failed to load. Check errors above."
    exit 1
fi
