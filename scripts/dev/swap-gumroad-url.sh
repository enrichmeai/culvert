#!/usr/bin/env bash
#
# swap-gumroad-url.sh — Replace [link — add before publishing] placeholders
#                        with a real Gumroad URL across all Medium articles.
#
# Usage:
#   ./scripts/dev/swap-gumroad-url.sh https://yourname.gumroad.com/l/gcp-pipeline-book
#
# Idempotent: running twice is harmless (real URL won't match the placeholder).

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}[OK]  $*${NC}"; }
fail() { echo -e "${RED}[ERR] $*${NC}"; }
info() { echo -e "${YELLOW}      $*${NC}"; }
hdr()  { echo -e "\n${BLUE}── $* ──${NC}"; }

# ── Validate argument ──────────────────────────────────────────────────────────
if [[ $# -ne 1 ]]; then
  fail "Usage: $0 <gumroad-url>"
  info "Example: $0 https://yourname.gumroad.com/l/gcp-pipeline-book"
  exit 1
fi

GUMROAD_URL="$1"

if [[ ! "$GUMROAD_URL" =~ ^https?:// ]]; then
  fail "URL must start with http:// or https://"
  exit 1
fi

# ── Locate the Medium articles dir relative to this script ────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MEDIUM_DIR="${REPO_ROOT}/book/medium"

if [[ ! -d "$MEDIUM_DIR" ]]; then
  fail "Medium articles directory not found: ${MEDIUM_DIR}"
  exit 1
fi

PLACEHOLDER='[link — add before publishing]'
TOTAL_REPLACEMENTS=0

hdr "Substituting Gumroad URL in Medium articles"
info "URL: ${GUMROAD_URL}"
info "Dir: ${MEDIUM_DIR}"
echo ""

for md_file in "${MEDIUM_DIR}"/*.md; do
  [[ -f "$md_file" ]] || continue

  filename="$(basename "$md_file")"

  # Count occurrences before substitution
  count=$(grep -cF "$PLACEHOLDER" "$md_file" 2>/dev/null || true)

  if [[ "$count" -eq 0 ]]; then
    info "${filename}: no placeholders found (already replaced or not present)"
    continue
  fi

  # Perform in-place substitution (BSD + GNU sed compatible)
  sed -i.bak "s|\[link — add before publishing\]|${GUMROAD_URL}|g" "$md_file"
  rm -f "${md_file}.bak"

  TOTAL_REPLACEMENTS=$((TOTAL_REPLACEMENTS + count))
  pass "${filename}: replaced ${count} placeholder(s)"
done

echo ""
hdr "Done"
if [[ "$TOTAL_REPLACEMENTS" -gt 0 ]]; then
  pass "Total replacements: ${TOTAL_REPLACEMENTS}"
else
  info "No placeholders were found — already substituted or files unchanged."
fi
