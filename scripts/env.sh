# Source from repo root:  source scripts/env.sh
# Clears a stale VIRTUAL_ENV from another checkout (e.g. Assignment 6) so uv uses this project's .venv.
unset VIRTUAL_ENV
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_PROJECT_ENVIRONMENT="${ROOT}/.venv"
cd "$ROOT"
