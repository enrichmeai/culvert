#!/usr/bin/env bash
# =============================================================================
# Load CDP Test Data into BigQuery
# =============================================================================
# Loads customer_risk_profile test data for segment transform testing.
#
# Usage:
#   ./scripts/load_cdp_test_data.sh [project_id] [dataset]
# =============================================================================
set -euo pipefail

PROJECT_ID="${1:-joseph-antony-aruja}"
CDP_DATASET="${2:-cdp_generic}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/../tests/data"

TABLE="customer_risk_profile"
FILE="${DATA_DIR}/cdp_customer_risk_profile.json"
SCHEMA="customer_id:STRING,first_name:STRING,last_name:STRING,date_of_birth:DATE,status:STRING,account_count:INTEGER,total_balance:FLOAT,risk_score:INTEGER,risk_category:STRING,updated_at:TIMESTAMP"

echo "============================================"
echo "  CDP Test Data Loader"
echo "============================================"
echo "Project:  ${PROJECT_ID}"
echo "Dataset:  ${CDP_DATASET}"
echo "Table:    ${TABLE}"
echo "============================================"
echo ""

# Ensure dataset exists
bq --project_id="${PROJECT_ID}" mk --dataset --force \
    --location=europe-west2 \
    "${PROJECT_ID}:${CDP_DATASET}" 2>/dev/null || true

# Load data
if [ ! -f "${FILE}" ]; then
    echo "ERROR: Data file not found: ${FILE}"
    exit 1
fi

# Convert JSON array to NDJSON (bq load requires one object per line)
NDJSON_FILE="/tmp/cdp_${TABLE}_ndjson.json"
python3 -c "
import json, sys
data = json.load(open(sys.argv[1]))
for row in data:
    print(json.dumps(row))
" "${FILE}" > "${NDJSON_FILE}"

ROWS=$(wc -l < "${NDJSON_FILE}" | tr -d ' ')
echo "Loading ${ROWS} rows from ${FILE}"
echo "  → ${CDP_DATASET}.${TABLE}"
echo ""

bq --project_id="${PROJECT_ID}" load \
    --source_format=NEWLINE_DELIMITED_JSON \
    --replace \
    "${CDP_DATASET}.${TABLE}" \
    "${NDJSON_FILE}" \
    "${SCHEMA}"

# Verify
echo ""
COUNT=$(bq --project_id="${PROJECT_ID}" query --nouse_legacy_sql --format=csv \
    "SELECT COUNT(*) AS cnt FROM \`${PROJECT_ID}.${CDP_DATASET}.${TABLE}\`" 2>/dev/null | tail -1)
echo "Verified: ${CDP_DATASET}.${TABLE} = ${COUNT} rows"
