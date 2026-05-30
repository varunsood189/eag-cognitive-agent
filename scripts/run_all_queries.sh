#!/usr/bin/env bash
# Run all Session 7 target queries (a–h).
# Output goes to the terminal and to logs/agent7-run-<timestamp>.log
#
# Usage:
#   ./scripts/run_all_queries.sh
#   LOG_DIR=./my-logs ./scripts/run_all_queries.sh

set -uo pipefail
# shellcheck source=env.sh
source "$(dirname "$0")/env.sh"

LOG_DIR="${LOG_DIR:-logs}"
# Pause between presets so Gemini free tier (15 RPM) can recover
PRESET_DELAY="${PRESET_DELAY:-60}"

timestamp() {
  date '+%Y-%m-%dT%H:%M:%S%z' 2>/dev/null || date '+%Y-%m-%d %H:%M:%S'
}

mkdir -p "$LOG_DIR" state workspace workspace/papers
LOG_FILE="$LOG_DIR/agent7-run-$(date +%Y%m%d-%H%M%S).log"

echo "EAG Cognitive Agent — running all presets"
echo "Log file: $LOG_FILE"
echo "Preset delay: ${PRESET_DELAY}s (override with PRESET_DELAY=90)"
echo "Started: $(timestamp)"
echo ""

# Tee stdout/stderr to log and terminal for the rest of this script
exec > >(tee -a "$LOG_FILE") 2>&1

clean_state() {
  echo "--- Cleaning state/ and workspace/ ---"
  rm -rf state workspace
  mkdir -p state workspace workspace/papers
  if [[ -d papers ]]; then
    cp -n papers/*.md workspace/papers/ 2>/dev/null || true
  fi
}

run_preset() {
  local preset="$1"
  local comment="$2"
  echo ""
  echo "=========================================="
  echo "PRESET: $preset — $comment"
  echo "Time:   $(timestamp)"
  echo "=========================================="
  if uv run python agent7.py --preset "$preset"; then
    echo "[ok] preset $preset finished at $(timestamp)"
  else
    local code=$?
    echo "[FAILED] preset $preset (exit $code) at $(timestamp)" >&2
    FAILURES+=("$preset")
  fi
  if [[ -n "${3:-}" ]]; then
    echo "--- waiting ${PRESET_DELAY}s before next preset (rate-limit cushion) ---"
    sleep "$PRESET_DELAY"
  fi
}

FAILURES=()

clean_state

run_preset a "Shannon Wikipedia" delay
run_preset b "Tokyo + weather" delay
run_preset c1 "Mom's birthday + reminders" delay
# Durable memory: do NOT wipe state/ before c2
run_preset c2 "When is mom's birthday?" delay
run_preset d "Asyncio synthesis" delay
run_preset e "Index attention paper" delay
run_preset f1 "Index all papers" delay
# Persist state/ for f2 (indexed corpus)
run_preset f2 "Cross-run CoT query" delay
run_preset g "Semantic credit assignment" delay
run_preset h "ReAct vs CoT compare"

echo ""
echo "=========================================="
echo "Finished: $(timestamp)"
echo "Log saved: $LOG_FILE"
if ((${#FAILURES[@]} > 0)); then
  echo "Failed presets: ${FAILURES[*]}"
  exit 1
fi
echo "All presets completed successfully."
