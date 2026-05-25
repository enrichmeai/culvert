#!/usr/bin/env bash
# =============================================================================
# insert-product-urls.sh — Swap [link — add before publishing] placeholders
#                           in Medium articles for real product URLs.
#
# Usage:
#   ./scripts/publish/insert-product-urls.sh \
#       --gumroad https://yourname.gumroad.com/l/gcp-pipeline-book \
#       [--play-books https://play.google.com/store/books/details?id=...] \
#       [--amazon    https://www.amazon.co.uk/dp/...] \
#       [--medium-dir book/medium] \
#       [--dry-run]
#
# Idempotent: if no placeholders remain, exits 0 with a friendly note.
# =============================================================================
set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}[OK]  $*${NC}"; }
fail() { echo -e "${RED}[ERR] $*${NC}"; exit 1; }
info() { echo -e "${YELLOW}      $*${NC}"; }
hdr()  { echo -e "\n${CYAN}── $* ──${NC}"; }

# ── Defaults ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

GUMROAD_URL=""
PLAY_BOOKS_URL=""
AMAZON_URL=""
MEDIUM_DIR="${REPO_ROOT}/book/medium"
DRY_RUN=false

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --gumroad)      GUMROAD_URL="$2";    shift 2 ;;
        --play-books)   PLAY_BOOKS_URL="$2"; shift 2 ;;
        --amazon)       AMAZON_URL="$2";     shift 2 ;;
        --medium-dir)   MEDIUM_DIR="$2";     shift 2 ;;
        --dry-run)      DRY_RUN=true;        shift   ;;
        -h|--help)
            echo "Usage: $0 --gumroad <url> [--play-books <url>] [--amazon <url>]"
            echo "           [--medium-dir <path>] [--dry-run]"
            exit 0 ;;
        *)
            fail "Unknown argument: $1. Run with --help for usage." ;;
    esac
done

# ── Validate required args ────────────────────────────────────────────────────
[[ -z "$GUMROAD_URL" ]] && fail "--gumroad <url> is required."

for _url in "$GUMROAD_URL" "${PLAY_BOOKS_URL:-}" "${AMAZON_URL:-}"; do
    [[ -z "$_url" ]] && continue
    [[ "$_url" =~ ^https?:// ]] || fail "URL must start with http:// or https://: ${_url}"
done

[[ -d "$MEDIUM_DIR" ]] || fail "Medium articles directory not found: ${MEDIUM_DIR}"

# ── Build the replacement string ──────────────────────────────────────────────
# Primary link is always "Buy on Gumroad".
# If secondary URLs are provided they are appended as extra Markdown links.
PRIMARY_MD="[Buy on Gumroad](${GUMROAD_URL})"

SECONDARY_PARTS=""
[[ -n "$PLAY_BOOKS_URL" ]] && SECONDARY_PARTS+=" · [Google Play Books](${PLAY_BOOKS_URL})"
[[ -n "$AMAZON_URL" ]]     && SECONDARY_PARTS+=" · [Amazon](${AMAZON_URL})"

REPLACEMENT="${PRIMARY_MD}${SECONDARY_PARTS}"

PLACEHOLDER="[link — add before publishing]"

# ── Header ────────────────────────────────────────────────────────────────────
if $DRY_RUN; then
    hdr "DRY RUN — no files will be written"
else
    hdr "Inserting product URLs into Medium articles"
fi
log "Gumroad : ${GUMROAD_URL}"
[[ -n "$PLAY_BOOKS_URL" ]] && log "Play Books: ${PLAY_BOOKS_URL}"
[[ -n "$AMAZON_URL" ]]     && log "Amazon    : ${AMAZON_URL}"
log "Directory : ${MEDIUM_DIR}"
log "Replacement: ${REPLACEMENT}"
echo ""

# ── Process files ─────────────────────────────────────────────────────────────
TOTAL_FILES=0
TOTAL_CHANGES=0
TOTAL_SKIPPED=0

for md_file in "${MEDIUM_DIR}"/*.md; do
    [[ -f "$md_file" ]] || continue
    filename="$(basename "$md_file")"

    # Count occurrences in this file
    count=$(grep -cF "$PLACEHOLDER" "$md_file" 2>/dev/null || true)

    if [[ "$count" -eq 0 ]]; then
        info "${filename}: no placeholders — skipping"
        TOTAL_SKIPPED=$((TOTAL_SKIPPED + 1))
        continue
    fi

    TOTAL_FILES=$((TOTAL_FILES + 1))
    TOTAL_CHANGES=$((TOTAL_CHANGES + count))

    if $DRY_RUN; then
        echo -e "${CYAN}--- ${filename} (${count} change(s)) ---${NC}"
        # Show old and new lines side by side
        while IFS= read -r line_num_and_content; do
            # grep -n gives "linenum:content"
            lineno="${line_num_and_content%%:*}"
            old_line="${line_num_and_content#*:}"
            new_line="${old_line//"$PLACEHOLDER"/$REPLACEMENT}"
            echo -e "  ${YELLOW}L${lineno} OLD:${NC} ${old_line}"
            echo -e "  ${GREEN}L${lineno} NEW:${NC} ${new_line}"
            echo ""
        done < <(grep -nF "$PLACEHOLDER" "$md_file" 2>/dev/null || true)
    else
        # In-place substitution; escape special chars in replacement for sed
        # Use perl for reliable substitution (avoids sed delimiter conflicts with URLs)
        perl -i -pe "s|\Q${PLACEHOLDER}\E|${REPLACEMENT}|g" "$md_file"
        pass "${filename}: replaced ${count} placeholder(s)"
    fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
hdr "Summary"
if [[ "$TOTAL_CHANGES" -eq 0 ]]; then
    pass "No placeholders found across any files — already substituted or nothing to do."
elif $DRY_RUN; then
    info "Would replace ${TOTAL_CHANGES} placeholder(s) across ${TOTAL_FILES} file(s)."
    info "${TOTAL_SKIPPED} file(s) already clean."
    info "Re-run without --dry-run to apply changes."
else
    pass "Replaced ${TOTAL_CHANGES} placeholder(s) across ${TOTAL_FILES} file(s)."
    [[ "$TOTAL_SKIPPED" -gt 0 ]] && info "${TOTAL_SKIPPED} file(s) already clean."
fi
