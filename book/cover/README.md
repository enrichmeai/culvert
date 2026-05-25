# Book Cover Assets

This folder contains the print-ready cover assets for
*Building Production-Grade Data Pipelines on Google Cloud*.

## Files

| File | Description |
|---|---|
| `book-cover-front.svg` | Front cover — 1410 × 2250 px, pure SVG |
| `book-cover-back.svg` | Back cover — 1410 × 2250 px, pure SVG |
| `book-cover-front-300dpi.png` | Front cover rasterised at 300 DPI (Amazon KDP ready) |
| `book-cover-back-300dpi.png` | Back cover rasterised at 300 DPI |

## Placeholder slots

Before submitting to a publisher, replace these two placeholders:

```bash
# Replace publisher name (e.g. "Leanpub", "Apress", "Self")
grep -rl '<PUBLISHER>' . | xargs sed -i 's/<PUBLISHER>/YourPublisherName/g'

# Replace ISBN
grep -rl '<PLACEHOLDER>' . | xargs sed -i 's/<PLACEHOLDER>/978-X-XXXXX-XXX-X/g'
```

## Converting SVG → PDF

### Option 1: Inkscape (recommended)
```bash
inkscape --export-type=pdf book-cover-front.svg
inkscape --export-type=pdf book-cover-back.svg
```

### Option 2: ImageMagick (SVG → PNG only; PDF blocked by default security policy)
```bash
convert -density 300 book-cover-front.svg book-cover-front.pdf   # may be blocked
convert -density 300 book-cover-front.svg book-cover-front.png   # always works
```

To lift the ImageMagick PDF restriction, edit `/etc/ImageMagick-6/policy.xml` and
change the `PDF` policy rights from `none` to `read|write`.

### Option 3: rsvg-convert
```bash
rsvg-convert -f pdf -o book-cover-front.pdf book-cover-front.svg
```

### Option 4: Chrome / Chromium headless
```bash
chromium --headless --print-to-pdf=book-cover-front.pdf \
  --print-to-pdf-no-header \
  book-cover-front.svg
```

## PDF → PNG at 300 DPI (Amazon KDP)

Once you have a PDF:
```bash
pdftocairo -png -r 300 book-cover-front.pdf book-cover-front
# Produces: book-cover-front-1.png
```

## Design notes

- Font stack: `DejaVu Sans, Helvetica, Arial, sans-serif` — no web fonts required.
- Palette: six framework colours (blue `#3B82F6`, green `#10B981`, yellow `#F59E0B`,
  purple `#8B5CF6`, grey `#6B7280`, red `#EF4444`) appear in the top band on both covers.
- Background navy: `#0F172A`. Bottom band charcoal: `#1E293B`.
- All text x-coordinates are within the safe inner margin (120 px left, 1290 px right).
