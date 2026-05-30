#!/usr/bin/env bash
# Copy Kaggle CSV into data/ai_jobs/raw/ then rebuild corpus + index.
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "$0")/env.sh"

SRC="${1:-$HOME/Downloads/ai_jobs_market_2025_2026.csv}"
DEST="$ROOT/data/ai_jobs/raw/ai_jobs_market_2025_2026.csv"

if [[ ! -f "$SRC" ]]; then
  echo "Source not found: $SRC" >&2
  echo "Usage: $0 [/path/to/ai_jobs_market_2025_2026.csv]" >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST")"
cp "$SRC" "$DEST"
echo "Copied to $DEST"
uv run python scripts/inspect_ai_jobs_csv.py
uv run python scripts/build_ai_jobs_corpus.py
echo "Run: uv run python scripts/index_ai_jobs_corpus.py  (1500 embeds; several minutes)"
