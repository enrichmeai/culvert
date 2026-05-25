#!/usr/bin/env bash
#
# submit-beam-job.sh — Submit a Beam pipeline to the Flink session cluster as
#                      a FlinkSessionJob resource.
#
# Usage:
#   ./bin/submit-beam-job.sh \
#     --entity      <name>         Entity name (e.g. customers)
#     --extract-date <YYYYMMDD>    Extract date (e.g. 20260512)
#     --jar-uri     <gs://...>     GCS URI for the Beam FAT-JAR
#     [--namespace  <ns>]          Kubernetes namespace (default: pipeline)
#
# Example:
#   ./bin/submit-beam-job.sh \
#     --entity customers \
#     --extract-date 20260512 \
#     --jar-uri gs://pipeline-artifacts/beam-pipelines/customers-ingestion.jar
#
# Prerequisites:
#   - kubectl configured and pointing at the target cluster
#   - envsubst available (part of gettext; brew install gettext on macOS)
#   - The pipeline-beam-runner Helm chart installed in --namespace
#
# The script reads examples/flinksessionjob-ingestion.yaml (relative to this
# chart root), substitutes ${ENTITY}, ${EXTRACT_DATE}, and ${JAR_URI} via
# envsubst, then applies the manifest and watches the job until RUNNING/FAILED.

set -euo pipefail

# ------------------------------------------------------------------------------
# Colour helpers - match the style used across scripts/airflow-local/
# ------------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'   # no colour

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}PASS $*${NC}"; }
fail() { echo -e "${RED}FAIL $*${NC}"; }
info() { echo -e "${YELLOW}   $*${NC}"; }
hdr()  { echo -e "${BLUE}=== $* ===${NC}"; }

# ------------------------------------------------------------------------------
# Argument parsing
# ------------------------------------------------------------------------------
ENTITY=""
EXTRACT_DATE=""
JAR_URI=""
NS="pipeline"

usage() {
  echo "Usage: $0 --entity <name> --extract-date <YYYYMMDD> --jar-uri <gs://...> [--namespace <ns>]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --entity)        ENTITY="$2";       shift 2 ;;
    --extract-date)  EXTRACT_DATE="$2"; shift 2 ;;
    --jar-uri)       JAR_URI="$2";      shift 2 ;;
    --namespace)     NS="$2";           shift 2 ;;
    -h|--help)       usage ;;
    *)               fail "Unknown argument: $1"; usage ;;
  esac
done

# ------------------------------------------------------------------------------
# Validate required args
# ------------------------------------------------------------------------------
if [[ -z "$ENTITY" || -z "$EXTRACT_DATE" || -z "$JAR_URI" ]]; then
  fail "Missing required arguments."
  usage
fi

if [[ ! "$EXTRACT_DATE" =~ ^[0-9]{8}$ ]]; then
  fail "--extract-date must be in YYYYMMDD format, got: $EXTRACT_DATE"
  exit 1
fi

# Job name must be lowercase DNS-compatible; entity should already be so.
JOB_NAME="pipeline-ingestion-${ENTITY}-${EXTRACT_DATE}"

# ------------------------------------------------------------------------------
# Locate template relative to this script's directory (chart root)
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHART_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE="${CHART_ROOT}/examples/flinksessionjob-ingestion.yaml"

if [[ ! -f "$TEMPLATE" ]]; then
  fail "Template not found: $TEMPLATE"
  exit 1
fi

# ------------------------------------------------------------------------------
# Export vars so envsubst can see them
# ------------------------------------------------------------------------------
export ENTITY EXTRACT_DATE JAR_URI

# ------------------------------------------------------------------------------
# Render manifest to a temp file
# ------------------------------------------------------------------------------
RENDERED=$(mktemp /tmp/flinksessionjob-XXXXXX.yaml)
trap 'rm -f "$RENDERED"' EXIT

envsubst < "$TEMPLATE" > "$RENDERED"

hdr "Submitting Beam pipeline to Flink"
info "Entity:        $ENTITY"
info "Extract date:  $EXTRACT_DATE"
info "JAR URI:       $JAR_URI"
info "Namespace:     $NS"
info "Job name:      $JOB_NAME"
info "Manifest:      $RENDERED"
echo ""

# ------------------------------------------------------------------------------
# Apply the manifest
# ------------------------------------------------------------------------------
log "Applying FlinkSessionJob manifest..."
kubectl apply -f "$RENDERED" -n "$NS"
pass "Manifest applied: $JOB_NAME"

# ------------------------------------------------------------------------------
# Watch until RUNNING or FAILED (timeout 10 minutes / 60 polls at 10s each)
# ------------------------------------------------------------------------------
hdr "Watching job status"
log "Polling FlinkSessionJob/$JOB_NAME in namespace $NS (timeout: 10 min)..."

MAX_POLLS=60
for i in $(seq 1 $MAX_POLLS); do
  STATE=$(kubectl get flinksessionjob "$JOB_NAME" -n "$NS" \
    -o jsonpath='{.status.jobStatus.state}' 2>/dev/null || echo "UNKNOWN")

  case "$STATE" in
    RUNNING)
      pass "Job $JOB_NAME is RUNNING (poll $i / $MAX_POLLS)"
      echo ""
      hdr "Useful commands"
      info "Watch logs:      kubectl logs -n $NS -l job-name=$JOB_NAME -f"
      info "Describe job:    kubectl describe flinksessionjob/$JOB_NAME -n $NS"
      info "Flink web UI:    kubectl port-forward svc/pipeline-beam-runner-rest -n $NS 8081:8081"
      exit 0
      ;;
    FAILED|FINISHED)
      fail "Job $JOB_NAME finished with state: $STATE (poll $i / $MAX_POLLS)"
      info "Inspect with: kubectl describe flinksessionjob/$JOB_NAME -n $NS"
      exit 1
      ;;
    *)
      info "State: ${STATE:-<pending>} (poll $i / $MAX_POLLS)"
      sleep 10
      ;;
  esac
done

fail "Timed out waiting for job $JOB_NAME to reach RUNNING state."
info "Check manually: kubectl get flinksessionjob/$JOB_NAME -n $NS"
exit 1
