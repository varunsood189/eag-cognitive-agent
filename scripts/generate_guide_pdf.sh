#!/usr/bin/env bash
# Generate docs/project-guide.pdf from HTML (Chromium print)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HTML="$ROOT/docs/project-guide.html"
PDF="$ROOT/docs/project-guide.pdf"

if [[ ! -f "$HTML" ]]; then
  echo "Missing $HTML" >&2
  exit 1
fi

CHROME=""
for c in chromium google-chrome chromium-browser; do
  if command -v "$c" &>/dev/null; then
    CHROME="$c"
    break
  fi
done

if [[ -z "$CHROME" ]]; then
  echo "Need chromium or google-chrome for PDF generation." >&2
  exit 1
fi

FILE_URL="file://${HTML}"
"$CHROME" \
  --headless=new \
  --disable-gpu \
  --no-sandbox \
  --run-all-compositor-stages-before-draw \
  --virtual-time-budget=3000 \
  --print-to-pdf="$PDF" \
  --print-to-pdf-no-header \
  --no-pdf-header-footer \
  "$FILE_URL" 2>/dev/null || \
"$CHROME" \
  --headless \
  --disable-gpu \
  --no-sandbox \
  --print-to-pdf="$PDF" \
  --print-to-pdf-no-header \
  "$FILE_URL"

if [[ -f "$PDF" ]]; then
  echo "Created: $PDF ($(wc -c < "$PDF") bytes)"
else
  echo "PDF generation failed." >&2
  exit 1
fi
