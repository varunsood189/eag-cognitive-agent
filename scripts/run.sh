#!/usr/bin/env bash
# Run commands in this project's uv environment (avoids Assignment 6 VIRTUAL_ENV warning).
# Usage: ./scripts/run.sh python agent7.py --preset a
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "$0")/env.sh"
exec uv run "$@"
