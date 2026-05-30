#!/usr/bin/env bash
# Write docs/traces/custom-q1..q5 with-index and no-index via jobs_rag.py
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "$0")/env.sh"

if [[ ! -f state_jobs/index.faiss ]]; then
  echo "Indexing corpus first (1500 items; several minutes)..."
  uv run python scripts/index_ai_jobs_corpus.py
fi

mkdir -p docs/traces
for q in q1 q2 q3 q4 q5; do
  echo "=== $q traces ==="
  uv run python jobs_rag.py --preset "$q" --write-traces
done
echo "Traces written under docs/traces/"
