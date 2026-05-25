#!/usr/bin/env bash
#
# seed-gcs.sh — Upload test_data/ fixtures into the fake GCS server.
#
# Creates buckets: generic-landing, generic-error-bucket, generic-archive
# Uploads every *.csv and *.ok from test_data/ into the landing bucket,
# named by entity: gs://generic-landing/<entity>/<filename>.

set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
info() { echo -e "${YELLOW}   $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GCS_HOST="${GCS_HOST:-http://localhost:4443}"

BUCKETS=(generic-landing generic-error-bucket generic-archive)

# Basic reachability check
if ! curl -fs "$GCS_HOST/storage/v1/b?project=local" >/dev/null; then
  fail "fake-gcs-server not reachable at $GCS_HOST. Is the stack up?"
  exit 1
fi

log "Creating buckets"
for b in "${BUCKETS[@]}"; do
  code=$(curl -o /dev/null -s -w "%{http_code}" \
    -X POST -H "Content-Type: application/json" \
    -d "{\"name\":\"$b\"}" \
    "$GCS_HOST/storage/v1/b?project=local")
  case "$code" in
    200|409) info "bucket $b ready" ;;
    *)       fail "bucket $b create failed (HTTP $code)"; exit 1 ;;
  esac
done

log "Uploading test_data fixtures"
cd "$REPO_ROOT/test_data"
for f in *.csv *.ok; do
  [ -f "$f" ] || continue
  # Entity inferred from filename: generic_<entity>_<date>.ext
  entity="$(echo "$f" | sed -E 's/^generic_([a-z]+)_.*$/\1/')"
  [ "$entity" = "$f" ] && entity="misc"
  dest="$entity/$f"
  curl -fs -X POST --data-binary "@$f" \
    -H "Content-Type: text/plain" \
    "$GCS_HOST/upload/storage/v1/b/generic-landing/o?uploadType=media&name=$dest" \
    >/dev/null || { fail "upload failed: $f"; exit 1; }
  info "uploaded $f -> gs://generic-landing/$dest"
done

pass "GCS seeded."
