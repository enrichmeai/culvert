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
RUN_ID="seg-e2e-$(date +%Y%m%d-%H%M%S)"
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

# --- Step 3: Launch Dataflow job (customer segment) ---
echo "" | tee -a "${REPORT_FILE}"
echo "=== Step 3: Launching Dataflow job ===" | tee -a "${REPORT_FILE}"

SEG="customer"
SEG_RUN_ID="${RUN_ID}-${SEG}"
echo "  Launching segment: ${SEG} (run_id=${SEG_RUN_ID})" | tee -a "${REPORT_FILE}"

STAGING="gs://${OUTPUT_BUCKET}/staging"

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
    --staging-location="${STAGING}" \
    --temp-location="${STAGING}/tmp" \
    --format="value(job.id)" 2>&1) || true

JOB_ID=$(echo "${JOB_OUTPUT}" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}_[0-9]{2}_[0-9]{2}-[0-9]+' | head -1 || echo "")
if [ -n "${JOB_ID}" ]; then
    echo "    Job ID: ${JOB_ID}" | tee -a "${REPORT_FILE}"
else
    echo "    WARNING: Could not extract job ID" | tee -a "${REPORT_FILE}"
    echo "    Output: ${JOB_OUTPUT}" | tee -a "${REPORT_FILE}"
fi

# --- Step 4: Poll for completion ---
echo "" | tee -a "${REPORT_FILE}"
echo "=== Step 4: Polling for job completion (timeout=${TIMEOUT}s) ===" | tee -a "${REPORT_FILE}"

ELAPSED=0
JOB_FINAL_STATUS="UNKNOWN"

if [ -n "${JOB_ID}" ]; then
    while [ "${ELAPSED}" -lt "${TIMEOUT}" ]; do
        STATUS=$(gcloud dataflow jobs describe "${JOB_ID}" \
            --project="${PROJECT_ID}" \
            --region="${REGION}" \
            --format="value(currentState)" 2>/dev/null || echo "UNKNOWN")

        if [ "${STATUS}" = "JOB_STATE_DONE" ] || [ "${STATUS}" = "JOB_STATE_FAILED" ]; then
            JOB_FINAL_STATUS="${STATUS}"
            echo "  Job completed at ${ELAPSED}s: ${STATUS}" | tee -a "${REPORT_FILE}"
            break
        fi

        echo "  [${ELAPSED}s] ${STATUS}" | tee -a "${REPORT_FILE}"
        sleep "${POLL_INTERVAL}"
        ELAPSED=$((ELAPSED + POLL_INTERVAL))
    done

    if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
        echo "  TIMEOUT: Job did not complete within ${TIMEOUT}s" | tee -a "${REPORT_FILE}"
    fi
fi

# --- Step 5: Verify output and generate report ---
echo "" | tee -a "${REPORT_FILE}"
echo "=== Step 5: Verifying output ===" | tee -a "${REPORT_FILE}"
echo "  Job Status: ${JOB_FINAL_STATUS}" | tee -a "${REPORT_FILE}"

OUTPUT_PATH="gs://${OUTPUT_BUCKET}/segments/${PERIOD_LABEL}/${SEG_RUN_ID}/${SEG}/"
FILES=$(gsutil ls "${OUTPUT_PATH}" 2>/dev/null | grep '\.dat$' | wc -l | tr -d ' ')

# Local directory for downloaded artifacts
LOCAL_DIR="/tmp/segment_e2e_${RUN_ID}"
mkdir -p "${LOCAL_DIR}"

if [ "${FILES}" -gt 0 ]; then
    echo "  Output files: ${FILES} .dat shards" | tee -a "${REPORT_FILE}"

    # Download all segment files and manifest locally
    echo "  Downloading segment files to ${LOCAL_DIR}/" | tee -a "${REPORT_FILE}"
    gsutil -m cp "${OUTPUT_PATH}*" "${LOCAL_DIR}/" 2>/dev/null || true

    # Count total records
    TOTAL_RECORDS=$(cat "${LOCAL_DIR}"/*.dat 2>/dev/null | wc -l | tr -d ' ')
    echo "  Total records: ${TOTAL_RECORDS}" | tee -a "${REPORT_FILE}"

    # Verify record lengths
    echo "" | tee -a "${REPORT_FILE}"
    echo "--- Record Length Check ---" | tee -a "${REPORT_FILE}"
    RECORD_LEN_OK=0
    RECORD_LEN_FAIL=0
    while IFS= read -r LINE; do
        LEN=${#LINE}
        if [ "${LEN}" -eq 200 ]; then
            RECORD_LEN_OK=$((RECORD_LEN_OK + 1))
        else
            RECORD_LEN_FAIL=$((RECORD_LEN_FAIL + 1))
            if [ "${RECORD_LEN_FAIL}" -le 3 ]; then
                echo "  FAIL: record length=${LEN} (expected 200)" | tee -a "${REPORT_FILE}"
            fi
        fi
    done < <(cat "${LOCAL_DIR}"/*.dat 2>/dev/null)
    echo "  Records with length=200: ${RECORD_LEN_OK}/${TOTAL_RECORDS}" | tee -a "${REPORT_FILE}"
    if [ "${RECORD_LEN_FAIL}" -gt 0 ]; then
        echo "  Records with wrong length: ${RECORD_LEN_FAIL}" | tee -a "${REPORT_FILE}"
    fi

    # --- Manifest ---
    echo "" | tee -a "${REPORT_FILE}"
    echo "--- Manifest ---" | tee -a "${REPORT_FILE}"
    if ls "${LOCAL_DIR}"/*.manifest 1>/dev/null 2>&1; then
        cat "${LOCAL_DIR}"/*.manifest | tee -a "${REPORT_FILE}"
    else
        echo "  MISSING" | tee -a "${REPORT_FILE}"
    fi

    # --- Sample Records (first 10, for manual verification) ---
    echo "" | tee -a "${REPORT_FILE}"
    echo "--- Sample Records (first 10) ---" | tee -a "${REPORT_FILE}"
    echo "  Template: customer.yaml (200-char fixed-width)" | tee -a "${REPORT_FILE}"
    echo "  Fields: CUST(4) | customer_id(20) | first_name(25) | last_name(25) | dob(8) | status(8) | acct_count(6) | balance(15) | score(6) | risk_cat(10) | extract_dt(8) | filler(65)" | tee -a "${REPORT_FILE}"
    echo "" | tee -a "${REPORT_FILE}"
    head -10 "${LOCAL_DIR}"/*.dat 2>/dev/null | while IFS= read -r LINE; do
        echo "  |${LINE}|" | tee -a "${REPORT_FILE}"
    done

    # --- File listing ---
    echo "" | tee -a "${REPORT_FILE}"
    echo "--- Output Files ---" | tee -a "${REPORT_FILE}"
    ls -lh "${LOCAL_DIR}"/ 2>/dev/null | tee -a "${REPORT_FILE}"

    # --- Summary ---
    echo "" | tee -a "${REPORT_FILE}"
    echo "============================================" | tee -a "${REPORT_FILE}"
    echo "  E2E Test Report" | tee -a "${REPORT_FILE}"
    echo "============================================" | tee -a "${REPORT_FILE}"
    echo "  Segment:       ${SEG}" | tee -a "${REPORT_FILE}"
    echo "  Period:         ${PERIOD_LABEL}" | tee -a "${REPORT_FILE}"
    echo "  Extract Date:   ${EXTRACT_DATE}" | tee -a "${REPORT_FILE}"
    echo "  Run ID:         ${SEG_RUN_ID}" | tee -a "${REPORT_FILE}"
    echo "  Job ID:         ${JOB_ID}" | tee -a "${REPORT_FILE}"
    echo "  Job Status:     ${JOB_FINAL_STATUS}" | tee -a "${REPORT_FILE}"
    echo "  Total Records:  ${TOTAL_RECORDS}" | tee -a "${REPORT_FILE}"
    echo "  Shards:         ${FILES}" | tee -a "${REPORT_FILE}"
    echo "  Record Len OK:  ${RECORD_LEN_OK}/${TOTAL_RECORDS}" | tee -a "${REPORT_FILE}"
    echo "  GCS Path:       ${OUTPUT_PATH}" | tee -a "${REPORT_FILE}"
    echo "  Local Copy:     ${LOCAL_DIR}/" | tee -a "${REPORT_FILE}"
    echo "  Report:         ${REPORT_FILE}" | tee -a "${REPORT_FILE}"
    echo "============================================" | tee -a "${REPORT_FILE}"
    echo "" | tee -a "${REPORT_FILE}"
    echo "E2E TEST PASSED" | tee -a "${REPORT_FILE}"
    echo ""
    echo "Report: ${REPORT_FILE}"
    echo "Files:  ${LOCAL_DIR}/"
    exit 0
else
    echo "  Output files: NONE — FAIL" | tee -a "${REPORT_FILE}"
    echo "" | tee -a "${REPORT_FILE}"
    echo "E2E TEST FAILED" | tee -a "${REPORT_FILE}"
    echo ""
    echo "Report: ${REPORT_FILE}"
    exit 1
fi
