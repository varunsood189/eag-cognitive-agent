#!/usr/bin/env bash
# Build docs/EAG_Cognitive_Agent_Architecture.pdf from Markdown + print CSS (Chromium).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MD="$ROOT/docs/EAG_Cognitive_Agent_Architecture.md"
CSS="$ROOT/docs/architecture-pdf.css"
HTML="$ROOT/docs/EAG_Cognitive_Agent_Architecture.html"
PDF="$ROOT/docs/EAG_Cognitive_Agent_Architecture.pdf"

if [[ ! -f "$MD" ]]; then
  echo "Missing $MD" >&2
  exit 1
fi
if [[ ! -f "$CSS" ]]; then
  echo "Missing $CSS" >&2
  exit 1
fi

pandoc "$MD" -s -t html5 \
  --from markdown+raw_html \
  --css "architecture-pdf.css" \
  -V lang=en \
  -o "$HTML"

CHROME=""
for c in chromium google-chrome chromium-browser; do
  if command -v "$c" >/dev/null 2>&1; then
    CHROME="$c"
    break
  fi
done

if [[ -z "$CHROME" ]]; then
  echo "No Chromium/Chrome found. Open and print to PDF:" >&2
  echo "  file://$HTML" >&2
  exit 1
fi

FILE_URL="file://${HTML}"
if ! "$CHROME" \
  --headless=new \
  --disable-gpu \
  --no-sandbox \
  --run-all-compositor-stages-before-draw \
  --virtual-time-budget=3000 \
  --print-to-pdf="$PDF" \
  --print-to-pdf-no-header \
  --no-pdf-header-footer \
  "$FILE_URL" 2>/dev/null; then
  "$CHROME" --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$PDF" "$FILE_URL" 2>/dev/null
fi

if [[ ! -f "$PDF" ]]; then
  echo "PDF generation failed. Try: $CHROME --headless --print-to-pdf=$PDF $FILE_URL" >&2
  exit 1
fi

echo "Wrote $PDF"
ls -lh "$PDF"
