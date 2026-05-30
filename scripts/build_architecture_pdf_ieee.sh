#!/usr/bin/env bash
# Build docs/EAG_Cognitive_Agent_Architecture_IEEE.pdf (IEEE conference layout).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MD="$ROOT/docs/EAG_Cognitive_Agent_Architecture_IEEE.md"
CSS="$ROOT/docs/ieee-architecture-pdf.css"
HTML="$ROOT/docs/EAG_Cognitive_Agent_Architecture_IEEE.html"
PDF="$ROOT/docs/EAG_Cognitive_Agent_Architecture_IEEE.pdf"

if [[ ! -f "$MD" ]]; then
  echo "Missing $MD" >&2
  exit 1
fi
if [[ ! -f "$CSS" ]]; then
  echo "Missing $CSS" >&2
  exit 1
fi

(
  cd "$ROOT/docs"
  pandoc "$(basename "$MD")" -s -t html5 \
    --from markdown+raw_html \
    --css "$(basename "$CSS")" \
    -V lang=en \
    -o "$(basename "$HTML")"
)

FILE_URL="file://${HTML}"
print_pdf() {
  local browser="$1"
  rm -f "$PDF"
  if "$browser" \
    --headless=new \
    --disable-gpu \
    --no-sandbox \
    --run-all-compositor-stages-before-draw \
    --virtual-time-budget=3000 \
    --print-to-pdf="$PDF" \
    --print-to-pdf-no-header \
    --no-pdf-header-footer \
    "$FILE_URL" 2>/dev/null; then
    [[ -f "$PDF" ]] && return 0
  fi
  if "$browser" --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$PDF" "$FILE_URL" 2>/dev/null; then
    [[ -f "$PDF" ]] && return 0
  fi
  return 1
}

CHROME=""
for c in google-chrome chromium chromium-browser; do
  if command -v "$c" >/dev/null 2>&1 && print_pdf "$c"; then
    CHROME="$c"
    break
  fi
done

if [[ -z "$CHROME" || ! -f "$PDF" ]]; then
  echo "PDF generation failed. Open and print to PDF:" >&2
  echo "  file://$HTML" >&2
  exit 1
fi

echo "Wrote $PDF"
ls -lh "$PDF"
