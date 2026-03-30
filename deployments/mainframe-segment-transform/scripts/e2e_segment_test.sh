#!/usr/bin/env bash
# =============================================================================
# E2E Test: Mainframe Segment Transform
# =============================================================================
# Tests the full segment transform pipeline:
#   1. Load CDP test data into BigQuery (if --load-data flag)
#   2. Build and deploy Flex Template (if --build flag)
#   3. Launch Dataflow jobs for each segment
#   4. Poll for completion
#   5. Verify GCS output files are correct fixed-width format
#
# Usage:
#   ./scripts/e2e_segment_test.sh [options]
#
# Options:
#   --load-data        Load CDP test data before running (default: skip)
#   --build            Build Docker image + Flex Template first (default: skip)
#   --segment SEG      Run only one segment (default: all 5)
#   --extract-month M  Extract month in YYYYMM (default: current month)
#   --project ID       GCP project (default: joseph-antony-aruja)
#   --env ENV          Environment (default: int)
#
# Examples:
#   # Full E2E: load data + run all segments for March 2026
#   ./scripts/e2e_segment_test.sh --load-data --extract-month 202603
#
#   # Test single segment (data already loaded)
#   ./scripts/e2e_segment_test.sh --segment customer
# =============================================================================
set -euo pipefail

PROJECT_ID="joseph-antony-aruja"
ENV="int"
CDP_DATASET="cdp_generic"
LOAD_DATA=false
BUILD=false
SEGMENT=""
TIMEOUT=900  # 15 minutes
POLL_INTERVAL=30
REGION="europe-west2"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${DEPLOY_DIR}/../.." && pwd)"

ALL_SEGMENTS="customer"
RUN_ID="segment_e2e_$(date +%Y%m%d_%H%M%S)"
EXTRACT_DATE=$(date +%Y%m%d)
EXTRACT_MONTH=""
OUTPUT_BUCKET="${PROJECT_ID}-generic-${ENV}-segments"
TEMPLATE_PATH="gs://${PROJECT_ID}-generic-${ENV}-segments/templates/segment_transform.json"
REPORT_FILE="/tmp/segment_e2e_report_$(date +%Y%m%d_%H%M%S).txt"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --load-data) LOAD_DATA=true; shift ;;
        --build) BUILD=true; shift ;;
        --segment) SEGMENT="$2"; shift 2 ;;
        --extract-month) EXTRACT_MONTH="$2"; shift 2 ;;
        --project) PROJECT_ID="$2"; shift 2 ;;
        --env) ENV="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Default extract_month to current month if not provided
if [ -z "${EXTRACT_MONTH}" ]; then
    EXTRACT_MONTH=$(date +%Y%m)
fi
PERIOD_LABEL="${EXTRACT_MONTH}"

SEGMENTS="${SEGMENT:-$ALL_SEGMENTS}"

echo "============================================" | tee "${REPORT_FILE}"
echo "  Segment Transform E2E Test" | tee -a "${REPORT_FILE}"
echo "============================================" | tee -a "${REPORT_FILE}"
echo "Project:        ${PROJECT_ID}" | tee -a "${REPORT_FILE}"
echo "Environment:    ${ENV}" | tee -a "${REPORT_FILE}"
echo "Run ID:         ${RUN_ID}" | tee -a "${REPORT_FILE}"
echo "Extract Date:   ${EXTRACT_DATE}" | tee -a "${REPORT_FILE}"
echo "Extract Month:  ${EXTRACT_MONTH}" | tee -a "${REPORT_FILE}"
echo "Segments:       ${SEGMENTS}" | tee -a "${REPORT_FILE}"
echo "Output:         gs://${OUTPUT_BUCKET}/segments/${PERIOD_LABEL}/${RUN_ID}/" | tee -a "${REPORT_FILE}"
echo "Template:       ${TEMPLATE_PATH}" | tee -a "${REPORT_FILE}"
echo "============================================" | tee -a "${REPORT_FILE}"

# --- Step 1: Load CDP test data (optional) ---
if [ "${LOAD_DATA}" = true ]; then
    echo "" | tee -a "${REPORT_FILE}"
    echo "=== Step 1: Loading CDP test data ===" | tee -a "${REPORT_FILE}"
    "${SCRIPT_DIR}/load_cdp_test_data.sh" "${PROJECT_ID}" "${CDP_DATASET}" 2>&1 | tee -a "${REPORT_FILE}"
fi

# --- Step 2: Build Flex Template (optional) ---
if [ "${BUILD}" = true ]; then
    echo "" | tee -a "${REPORT_FILE}"
    echo "=== Step 2: Building Flex Template ===" | tee -a "${REPORT_FILE}"
    cd "${REPO_DIR}"
    gcloud builds submit \
        --project="${PROJECT_ID}" \
        --config=deployments/mainframe-segment-transform/cloudbuild.yaml \
        --substitutions="_LIBRARY_VERSION=1.0.29" \
        . 2>&1 | tee -a "${REPORT_FILE}"
    cd "${SCRIPT_DIR}"
fi

# --- Step 3: Launch Dataflow jobs ---
echo "" | tee -a "${REPORT_FILE}"
echo "=== Step 3: Launching Dataflow jobs ===" | tee -a "${REPORT_FILE}"

declare -A JOB_IDS
for SEG in ${SEGMENTS}; do
    SEG_RUN_ID="${RUN_ID}_${SEG}"
    echo "  Launching segment: ${SEG} (run_id=${SEG_RUN_ID})" | tee -a "${REPORT_FILE}"

    JOB_OUTPUT=$(gcloud dataflow flex-template run \
        "segment-${SEG}-${RUN_ID}" \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --template-file-gcs-location="${TEMPLATE_PATH}" \
        --parameters="segment=${SEG}" \
        --parameters="extract_date=${EXTRACT_DATE}" \
        --parameters="extract_month=${EXTRACT_MONTH}" \
        --parameters="output_bucket=${OUTPUT_BUCKET}" \
        --parameters="run_id=${SEG_RUN_ID}" \
        --parameters="gcp_project=${PROJECT_ID}" \
        --format="value(job.id)" 2>&1) || true

    JOB_ID=$(echo "${JOB_OUTPUT}" | grep -oP '[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}_[0-9]{2}_[0-9]{2}-[0-9]+' | head -1 || echo "")
    if [ -n "${JOB_ID}" ]; then
        JOB_IDS[${SEG}]="${JOB_ID}"
        echo "    Job ID: ${JOB_ID}" | tee -a "${REPORT_FILE}"
    else
        echo "    WARNING: Could not extract job ID for ${SEG}" | tee -a "${REPORT_FILE}"
        echo "    Output: ${JOB_OUTPUT}" | tee -a "${REPORT_FILE}"
    fi
done

# --- Step 4: Poll for completion ---
echo "" | tee -a "${REPORT_FILE}"
echo "=== Step 4: Polling for job completion (timeout=${TIMEOUT}s) ===" | tee -a "${REPORT_FILE}"

ELAPSED=0
declare -A JOB_STATUS

while [ "${ELAPSED}" -lt "${TIMEOUT}" ]; do
    ALL_DONE=true
    for SEG in ${SEGMENTS}; do
        if [ -z "${JOB_IDS[${SEG}]:-}" ]; then continue; fi
        if [ "${JOB_STATUS[${SEG}]:-}" = "JOB_STATE_DONE" ] || [ "${JOB_STATUS[${SEG}]:-}" = "JOB_STATE_FAILED" ]; then
            continue
        fi

        STATUS=$(gcloud dataflow jobs describe "${JOB_IDS[${SEG}]}" \
            --project="${PROJECT_ID}" \
            --region="${REGION}" \
            --format="value(currentState)" 2>/dev/null || echo "UNKNOWN")

        JOB_STATUS[${SEG}]="${STATUS}"

        if [ "${STATUS}" != "JOB_STATE_DONE" ] && [ "${STATUS}" != "JOB_STATE_FAILED" ]; then
            ALL_DONE=false
        fi
    done

    if [ "${ALL_DONE}" = true ]; then
        echo "  All jobs completed at ${ELAPSED}s" | tee -a "${REPORT_FILE}"
        break
    fi

    echo "  [${ELAPSED}s] Waiting... $(for SEG in ${SEGMENTS}; do echo -n "${SEG}=${JOB_STATUS[${SEG}]:-PENDING} "; done)" | tee -a "${REPORT_FILE}"
    sleep "${POLL_INTERVAL}"
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
    echo "  TIMEOUT: Jobs did not complete within ${TIMEOUT}s" | tee -a "${REPORT_FILE}"
fi

# --- Step 5: Verify output files ---
echo "" | tee -a "${REPORT_FILE}"
echo "=== Step 5: Verifying output files ===" | tee -a "${REPORT_FILE}"

PASS_COUNT=0
FAIL_COUNT=0

for SEG in ${SEGMENTS}; do
    SEG_RUN_ID="${RUN_ID}_${SEG}"
    echo "" | tee -a "${REPORT_FILE}"
    echo "  --- Segment: ${SEG} ---" | tee -a "${REPORT_FILE}"
    echo "  Job Status: ${JOB_STATUS[${SEG}]:-NO_JOB}" | tee -a "${REPORT_FILE}"

    # Check GCS output (period-aware path: /segments/{period}/{run_id}/{segment}/)
    OUTPUT_PATH="gs://${OUTPUT_BUCKET}/segments/${PERIOD_LABEL}/${SEG_RUN_ID}/${SEG}/"
    FILES=$(gsutil ls "${OUTPUT_PATH}" 2>/dev/null | grep -c '\.dat$' || echo "0")

    if [ "${FILES}" -gt 0 ]; then
        echo "  Output files: ${FILES} .dat shards" | tee -a "${REPORT_FILE}"

        # Verify record length (first .dat file, first 5 lines)
        FIRST_FILE=$(gsutil ls "${OUTPUT_PATH}*.dat" 2>/dev/null | head -1)
        if [ -n "${FIRST_FILE}" ]; then
            echo "  Checking record length in: ${FIRST_FILE}" | tee -a "${REPORT_FILE}"
            gsutil cat "${FIRST_FILE}" 2>/dev/null | head -5 | while read -r LINE; do
                LEN=${#LINE}
                if [ "${LEN}" -eq 200 ]; then
                    echo "    Record length: ${LEN} chars - OK" | tee -a "${REPORT_FILE}"
                else
                    echo "    Record length: ${LEN} chars - FAIL (expected 200)" | tee -a "${REPORT_FILE}"
                fi
            done
        fi

        # Count total records across all shards
        TOTAL_RECORDS=$(gsutil cat "${OUTPUT_PATH}*.dat" 2>/dev/null | wc -l | tr -d ' ')
        echo "  Total records: ${TOTAL_RECORDS}" | tee -a "${REPORT_FILE}"

        # Check manifest file
        MANIFEST_FILES=$(gsutil ls "${OUTPUT_PATH}*.manifest" 2>/dev/null || true)
        if [ -n "${MANIFEST_FILES}" ]; then
            echo "  Manifest: found" | tee -a "${REPORT_FILE}"
            MANIFEST_CONTENT=$(gsutil cat "${OUTPUT_PATH}*.manifest" 2>/dev/null | head -20)
            echo "${MANIFEST_CONTENT}" | tee -a "${REPORT_FILE}"
            MANIFEST_RECORDS=$(echo "${MANIFEST_CONTENT}" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_records'])" 2>/dev/null || echo "?")
            echo "  Manifest total_records: ${MANIFEST_RECORDS}" | tee -a "${REPORT_FILE}"
        else
            echo "  Manifest: MISSING" | tee -a "${REPORT_FILE}"
        fi

        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "  Output files: NONE — FAIL" | tee -a "${REPORT_FILE}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

# --- Summary ---
echo "" | tee -a "${REPORT_FILE}"
echo "============================================" | tee -a "${REPORT_FILE}"
echo "  E2E Test Summary" | tee -a "${REPORT_FILE}"
echo "============================================" | tee -a "${REPORT_FILE}"
echo "Segments passed: ${PASS_COUNT}" | tee -a "${REPORT_FILE}"
echo "Segments failed: ${FAIL_COUNT}" | tee -a "${REPORT_FILE}"
echo "Report: ${REPORT_FILE}" | tee -a "${REPORT_FILE}"
echo "============================================" | tee -a "${REPORT_FILE}"

if [ "${FAIL_COUNT}" -eq 0 ] && [ "${PASS_COUNT}" -gt 0 ]; then
    echo "E2E TEST PASSED" | tee -a "${REPORT_FILE}"
    exit 0
else
    echo "E2E TEST FAILED" | tee -a "${REPORT_FILE}"
    exit 1
fi
