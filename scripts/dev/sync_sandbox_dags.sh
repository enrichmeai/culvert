#!/usr/bin/env bash
#
# sync_sandbox_dags.sh — Upload DAGs to a developer's sandbox Composer env.
#
# Reads sandbox.env (written by setup_sandbox.sh) or takes --target <project>.
# Supports --dry-run for a preview-only rsync.
#
# The DAG factory (DagFactory / generate_dags.py) honours $DAG_PREFIX — this
# script sets it to the developer's username so sandbox DAGs are namespaced
# and do not collide with other developers' DAGs in a shared Composer env.
#
# Usage:
#   source sandbox.env
#   ./scripts/dev/sync_sandbox_dags.sh                 # normal sync
#   ./scripts/dev/sync_sandbox_dags.sh --dry-run       # show what would change
#   ./scripts/dev/sync_sandbox_dags.sh --target my-p   # override project

set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; }
info() { echo -e "${YELLOW}   $*${NC}"; }

DRY_RUN=false
TARGET_PROJECT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)   DRY_RUN=true; shift ;;
    --target)    TARGET_PROJECT="$2"; shift 2 ;;
    *)           fail "unknown arg: $1"; exit 1 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SANDBOX_ENV="$REPO_ROOT/sandbox.env"

if [ -z "$TARGET_PROJECT" ] && [ -f "$SANDBOX_ENV" ]; then
  # shellcheck disable=SC1090
  source "$SANDBOX_ENV"
  TARGET_PROJECT="$GCP_PROJECT_ID"
fi

if [ -z "$TARGET_PROJECT" ]; then
  fail "No target. Run setup_sandbox.sh first or pass --target <project>."
  exit 1
fi

USER_NAME="${USER:-dev}"
DAG_PREFIX="${DAG_PREFIX:-${USER_NAME}_}"
DAGS_BUCKET="${TARGET_PROJECT}-composer-dags"
DAGS_SRC="$REPO_ROOT/deployments/data-pipeline-orchestrator/dags"

log "Target project:  $TARGET_PROJECT"
log "DAGs bucket:     gs://$DAGS_BUCKET/dags/"
log "DAG_PREFIX:      $DAG_PREFIX"
log "Source:          $DAGS_SRC"
log "Dry run:         $DRY_RUN"

if ! command -v gsutil >/dev/null; then
  fail "gsutil not on PATH"; exit 1
fi

# Ensure the bucket exists
if ! gsutil ls -b "gs://$DAGS_BUCKET" >/dev/null 2>&1; then
  log "Creating DAGs bucket"
  gsutil mb -p "$TARGET_PROJECT" "gs://$DAGS_BUCKET" >/dev/null
fi

# Export DAG_PREFIX so DagFactory picks it up on the Composer side. The
# generate_dags.py script reads DAG_PREFIX from env and namespaces DAG IDs.
export DAG_PREFIX

log "Uploading DAGs…"
if $DRY_RUN; then
  gsutil -m rsync -r -n "$DAGS_SRC" "gs://$DAGS_BUCKET/dags/"
  info "(dry run only — nothing written)"
else
  gsutil -m rsync -r -d "$DAGS_SRC" "gs://$DAGS_BUCKET/dags/"
  pass "synced"
fi
