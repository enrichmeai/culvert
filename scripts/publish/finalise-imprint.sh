#!/usr/bin/env bash
#
# finalise-imprint.sh — Substitute publisher, ISBN, and VAT placeholders across
# all publish-ready artefacts in one shot.
#
# After running this, the book PDF / EPUB and cover SVGs are ready to upload to
# Gumroad, Google Play Books, and Amazon KDP under your company imprint.
#
# Usage:
#   ./scripts/publish/finalise-imprint.sh \
#       --publisher "Aruja Solutions" \
#       --isbn "978-1-XXXXXX-XX-X" \
#       --vat "123456789"
#
#   ./scripts/publish/finalise-imprint.sh --publisher "Aruja Solutions"
#       (skips ISBN and VAT — leaves those placeholders for later)
#
#   ./scripts/publish/finalise-imprint.sh --dry-run --publisher "..."
#       (shows what would change without writing)
#
# What it touches:
#   - book/cover/book-cover-front.svg
#   - book/cover/book-cover-back.svg
#   - book/cover/book-cover-front-300dpi.png    (regenerated if changes land)
#   - book/cover/book-cover-back-300dpi.png     (regenerated)
#   - book/gcp-pipeline-book.md                 (copyright page front matter)
#   - book/gcp-pipeline-book.pdf                (regenerated)
#   - book/gcp-pipeline-book.epub               (regenerated)
#
# Idempotent: safe to re-run with new values.

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; }
info() { echo -e "${YELLOW}   $*${NC}"; }
hdr()  { echo -e "\n${BLUE}── $* ──${NC}"; }

PUBLISHER=""
ISBN=""
VAT=""
DRY_RUN=false

while [ $# -gt 0 ]; do
  case "$1" in
    --publisher) PUBLISHER="$2"; shift 2 ;;
    --isbn)      ISBN="$2";      shift 2 ;;
    --vat)       VAT="$2";       shift 2 ;;
    --dry-run)   DRY_RUN=true;   shift ;;
    -h|--help)
      grep -E '^#( |!)' "$0" | sed -E 's/^# ?//'
      exit 0
      ;;
    *) fail "unknown arg: $1"; exit 1 ;;
  esac
done

if [ -z "$PUBLISHER" ]; then
  fail "Missing required --publisher \"Your Company\""
  echo
  echo "Try:  $0 --publisher 'Aruja Solutions' --isbn '978-1-XXXX' --vat '123456789'"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

hdr "Finalise imprint — Publisher: $PUBLISHER"
[ -n "$ISBN" ] && info "ISBN: $ISBN"
[ -n "$VAT" ]  && info "VAT:  $VAT"
$DRY_RUN && info "(dry run — no files will be modified)"

# Files we'll substitute in
FILES=(
  "book/cover/book-cover-front.svg"
  "book/cover/book-cover-back.svg"
  "book/gcp-pipeline-book.md"
)

# Build a substitution function that respects dry-run
substitute() {
  local file="$1"
  local placeholder="$2"
  local value="$3"

  if [ ! -f "$file" ]; then
    info "skip (not found): $file"
    return 0
  fi

  # How many instances to swap? (use grep -o so multiple per line are counted)
  # Note: grep exits 1 when no matches found; pipefail would kill us, so guard it.
  local count
  count=$( { grep -o -F "$placeholder" "$file" 2>/dev/null || true; } | wc -l | tr -d ' ')
  count=${count:-0}
  if [ "${count:-0}" = "0" ]; then
    return 0
  fi

  if $DRY_RUN; then
    info "would replace ${count}× ${placeholder} → ${value} in ${file}"
  else
    # Use perl to handle special chars safely
    perl -i -pe "s/\Q${placeholder}\E/${value}/g" "$file"
    info "replaced ${count}× ${placeholder} → ${value} in ${file}"
  fi
}

# Apply substitutions. Markdown uses literal "<PUBLISHER>"; SVG uses
# HTML-escaped "&lt;PUBLISHER&gt;" because raw < / > break XML parsing.
hdr "Applying substitutions"
for f in "${FILES[@]}"; do
  # Plain placeholders (Markdown / plain text)
  substitute "$f" "<PUBLISHER>" "$PUBLISHER"
  [ -n "$ISBN" ] && substitute "$f" "<ISBN>" "$ISBN"
  [ -n "$ISBN" ] && substitute "$f" "<PLACEHOLDER>" "$ISBN"
  [ -n "$VAT" ]  && substitute "$f" "<VAT>" "$VAT"

  # HTML-escaped placeholders (SVG)
  substitute "$f" "&lt;PUBLISHER&gt;" "$PUBLISHER"
  [ -n "$ISBN" ] && substitute "$f" "&lt;ISBN&gt;" "$ISBN"
  [ -n "$ISBN" ] && substitute "$f" "&lt;PLACEHOLDER&gt;" "$ISBN"
  [ -n "$VAT" ]  && substitute "$f" "&lt;VAT&gt;" "$VAT"
done

if $DRY_RUN; then
  pass "Dry run complete — no files were modified."
  exit 0
fi

# Regenerate book PDF + EPUB
hdr "Regenerating book PDF + EPUB"
cd "$REPO_ROOT/book"

if command -v pandoc >/dev/null; then
  pandoc gcp-pipeline-book.md -o gcp-pipeline-book.pdf \
      --pdf-engine=xelatex \
      --toc --toc-depth=2 \
      --top-level-division=chapter \
      -V geometry:margin=1in \
      -V mainfont="DejaVu Serif" \
      -V monofont="DejaVu Sans Mono" \
      -V sansfont="DejaVu Sans" \
      -V fontsize=11pt \
      -V linkcolor=NavyBlue \
      -V urlcolor=NavyBlue \
      -V toccolor=black \
      --highlight-style=tango \
    && pass "rebuilt gcp-pipeline-book.pdf" \
    || fail "PDF rebuild failed — check pandoc output above"

  pandoc gcp-pipeline-book.md -o gcp-pipeline-book.epub \
      --toc --toc-depth=2 \
      --metadata title="Building Production-Grade Data Pipelines on Google Cloud" \
      --metadata author="Joseph Aruja" \
      --metadata publisher="$PUBLISHER" \
      --metadata lang="en-GB" \
      --highlight-style=tango \
    && pass "rebuilt gcp-pipeline-book.epub" \
    || fail "EPUB rebuild failed"
else
  fail "pandoc not on PATH — skipping book rebuild. Run manually when ready."
fi

# Regenerate cover PNGs at 300 DPI
hdr "Regenerating cover PNGs (300 DPI for Amazon KDP / Play Books)"
cd "$REPO_ROOT"

if command -v rsvg-convert >/dev/null; then
  for side in front back; do
    rsvg-convert -d 300 -p 300 \
      "book/cover/book-cover-${side}.svg" \
      -o "book/cover/book-cover-${side}-300dpi.png" \
      && pass "rebuilt book-cover-${side}-300dpi.png"
  done
elif command -v inkscape >/dev/null; then
  for side in front back; do
    inkscape --export-type=png --export-dpi=300 \
      --export-filename="book/cover/book-cover-${side}-300dpi.png" \
      "book/cover/book-cover-${side}.svg" \
      && pass "rebuilt book-cover-${side}-300dpi.png"
  done
elif command -v convert >/dev/null; then
  for side in front back; do
    convert -density 300 -background white \
      "book/cover/book-cover-${side}.svg" \
      "book/cover/book-cover-${side}-300dpi.png" \
      && pass "rebuilt book-cover-${side}-300dpi.png (via ImageMagick)"
  done
else
  info "no SVG→PNG converter found. Install one of:"
  info "  brew install librsvg          # rsvg-convert (recommended)"
  info "  brew install inkscape         # full editor"
  info "  brew install imagemagick      # general-purpose"
  info "Then re-run this script (or just the PNG block manually)."
fi

hdr "Done"
pass "Publisher imprint finalised: $PUBLISHER"
[ -n "$ISBN" ] && pass "ISBN: $ISBN" || info "ISBN: still placeholder (pass --isbn next time)"
[ -n "$VAT" ]  && pass "VAT:  GB $VAT"  || info "VAT:  still placeholder (pass --vat next time)"

echo
echo "Next steps:"
echo "  1. Review book/gcp-pipeline-book.pdf — confirm the copyright page reads correctly."
echo "  2. Upload book + cover to your platforms (Gumroad / Play Books / KDP)."
echo "  3. Once Gumroad listing is live, run:"
echo "       ./scripts/publish/insert-product-urls.sh --gumroad <url>"
echo "     to replace the [link — add before publishing] placeholders across the 8 Medium articles."
