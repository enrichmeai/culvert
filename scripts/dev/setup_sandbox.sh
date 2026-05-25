#!/usr/bin/env bash
#
# setup_sandbox.sh — Provision a per-developer GCP sandbox project.
#
# Creates:
#   - GCP project `pipeline-sandbox-<user>`
#   - Billing link (if BILLING_ACCOUNT_ID is set)
#   - Enabled APIs matching scripts/gcp/01_enable_services.sh
#   - Service account `pipeline-sandbox-sa@<project>.iam.gserviceaccount.com`
#   - GCS buckets: <project>-landing, <project>-error, <project>-archive
#   - BigQuery dataset: odp_generic_sandbox_<user> (7-day table expiration)
#   - $100/month budget with 50% and 90% alerts
#
# Usage:
#   BILLING_ACCOUNT_ID=0X0X0X-0X0X0X-0X0X0X ./scripts/dev/setup_sandbox.sh
#   ./scripts/dev/setup_sandbox.sh --user bob

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; }
info() { echo -e "${YELLOW}   $*${NC}"; }
hdr()  { echo -e "\n${BLUE}── $* ──${NC}"; }

USER_NAME="${USER:-dev}"
if [ "${1:-}" = "--user" ] && [ -n "${2:-}" ]; then
  USER_NAME="$2"
fi
USER_NAME=$(echo "$USER_NAME" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-')
PROJECT_ID="pipeline-sandbox-${USER_NAME}"
SA_NAME="pipeline-sandbox-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
REGION="${REGION:-europe-west2}"

LANDING_BUCKET="${PROJECT_ID}-landing"
ERROR_BUCKET="${PROJECT_ID}-error"
ARCHIVE_BUCKET="${PROJECT_ID}-archive"
DATASET="odp_generic_sandbox_${USER_NAME//-/_}"

command -v gcloud >/dev/null || { fail "gcloud not found"; exit 1; }
command -v gsutil >/dev/null || { fail "gsutil not found"; exit 1; }
command -v bq     >/dev/null || { fail "bq not found"; exit 1; }

hdr "Sandbox: $PROJECT_ID"

# --- Project ------------------------------------------------------------- #
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  info "project $PROJECT_ID already exists"
else
  log "Creating project $PROJECT_ID"
  gcloud projects create "$PROJECT_ID" --name="Pipeline Sandbox $USER_NAME"
fi

# --- Billing link -------------------------------------------------------- #
if [ -n "${BILLING_ACCOUNT_ID:-}" ]; then
  log "Linking billing account $BILLING_ACCOUNT_ID"
  gcloud billing projects link "$PROJECT_ID" \
    --billing-account "$BILLING_ACCOUNT_ID" >/dev/null
  pass "billing linked"
else
  info "BILLING_ACCOUNT_ID not set; skipping billing link (APIs needing billing will fail to enable)"
fi

# --- APIs (mirror of scripts/gcp/01_enable_services.sh) ----------------- #
hdr "Enabling APIs"
APIS=(
  cloudresourcemanager.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  serviceusage.googleapis.com
  cloudbuild.googleapis.com
  artifactregistry.googleapis.com
  storage.googleapis.com
  bigquery.googleapis.com
  pubsub.googleapis.com
  dataflow.googleapis.com
  composer.googleapis.com
  logging.googleapis.com
  monitoring.googleapis.com
  cloudbilling.googleapis.com
)
for api in "${APIS[@]}"; do
  gcloud services enable "$api" --project="$PROJECT_ID" >/dev/null 2>&1 \
    && info "enabled $api" \
    || info "skipped $api (likely billing not linked)"
done

# --- Service account ----------------------------------------------------- #
hdr "Service account"
if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  info "SA $SA_EMAIL exists"
else
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="Pipeline sandbox SA" --project="$PROJECT_ID" >/dev/null
  pass "created $SA_EMAIL"
fi

for role in roles/storage.admin roles/bigquery.dataEditor roles/dataflow.developer roles/pubsub.editor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" --role="$role" \
    --condition=None >/dev/null
  info "granted $role"
done

# --- Buckets ------------------------------------------------------------- #
hdr "GCS buckets"
for b in "$LANDING_BUCKET" "$ERROR_BUCKET" "$ARCHIVE_BUCKET"; do
  if gsutil ls -b "gs://$b" >/dev/null 2>&1; then
    info "bucket gs://$b exists"
  else
    gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://$b" >/dev/null
    pass "created gs://$b"
  fi
done

# Lifecycle rule: auto-delete sandbox objects after 30 days of no access
LIFECYCLE_JSON=$(mktemp)
cat >"$LIFECYCLE_JSON" <<'JSON'
{"rule":[{"action":{"type":"Delete"},"condition":{"daysSinceNoncurrentTime":30}}]}
JSON
for b in "$LANDING_BUCKET" "$ERROR_BUCKET" "$ARCHIVE_BUCKET"; do
  gsutil lifecycle set "$LIFECYCLE_JSON" "gs://$b" >/dev/null || true
done
rm -f "$LIFECYCLE_JSON"
info "30-day lifecycle rule applied"

# --- BigQuery dataset with 7-day table expiration ------------------------ #
hdr "BigQuery dataset"
if bq --project_id="$PROJECT_ID" ls -d "${PROJECT_ID}:${DATASET}" >/dev/null 2>&1; then
  info "dataset $DATASET exists"
else
  bq --project_id="$PROJECT_ID" mk \
    --default_table_expiration 604800 \
    --location="$REGION" \
    "${PROJECT_ID}:${DATASET}" >/dev/null
  pass "created $DATASET (default 7-day table expiration)"
fi

# --- Budget alert -------------------------------------------------------- #
if [ -n "${BILLING_ACCOUNT_ID:-}" ]; then
  hdr "Budget alert ($100/month @ 50% + 90%)"
  BUDGET_NAME="sandbox-${USER_NAME}"
  gcloud billing budgets create \
    --billing-account "$BILLING_ACCOUNT_ID" \
    --display-name "$BUDGET_NAME" \
    --budget-amount 100USD \
    --threshold-rule=percent=0.5 \
    --threshold-rule=percent=0.9 \
    --filter-projects "projects/${PROJECT_ID}" \
    >/dev/null 2>&1 \
    && pass "budget created" \
    || info "budget may already exist (skipped)"
fi

# --- sandbox.env --------------------------------------------------------- #
hdr "Writing sandbox.env"
SANDBOX_ENV="$(cd "$(dirname "$0")/../.." && pwd)/sandbox.env"
cat >"$SANDBOX_ENV" <<EOF
# Generated by scripts/dev/setup_sandbox.sh
export GCP_PROJECT_ID=${PROJECT_ID}
export GCP_REGION=${REGION}
export PIPELINE_SANDBOX_SA=${SA_EMAIL}
export LANDING_BUCKET=${LANDING_BUCKET}
export ERROR_BUCKET=${ERROR_BUCKET}
export ARCHIVE_BUCKET=${ARCHIVE_BUCKET}
export BQ_DATASET=${DATASET}
export ENVIRONMENT=sandbox
EOF
pass "wrote $SANDBOX_ENV"

# --- Summary ------------------------------------------------------------- #
hdr "Sandbox ready"
cat <<EOF
  Project:          $PROJECT_ID
  Region:           $REGION
  Service account:  $SA_EMAIL
  Landing bucket:   gs://$LANDING_BUCKET
  Error bucket:     gs://$ERROR_BUCKET
  Archive bucket:   gs://$ARCHIVE_BUCKET
  BigQuery dataset: $DATASET

  Next steps:
    source sandbox.env
    gcloud config set project "$PROJECT_ID"
    gcloud auth application-default login
EOF
