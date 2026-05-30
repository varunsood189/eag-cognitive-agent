#!/usr/bin/env bash
# Part 2 — agent7 presets j1–j5 against state_jobs/ (index corpus first).
set -uo pipefail
# shellcheck source=env.sh
source "$(dirname "$0")/env.sh"

if [[ ! -f state_jobs/memory.json ]]; then
  echo "Missing state_jobs/. Run: python scripts/index_ai_jobs_corpus.py" >&2
  exit 1
fi

export EAG_STATE_DIR=state_jobs
LOG_DIR="${LOG_DIR:-logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/custom-agent7-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Custom agent7 queries (j1–j5) — state_jobs/"
for preset in j1 j2 j3 j4 j5; do
  echo ""
  echo "========== PRESET $preset =========="
  uv run python agent7.py --preset "$preset" || echo "[FAILED] $preset"
  sleep "${PRESET_DELAY:-45}"
done
echo "Log: $LOG_FILE"
