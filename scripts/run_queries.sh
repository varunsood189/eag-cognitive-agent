#!/usr/bin/env bash
# Wrapper — prefer ./scripts/run_all_queries.sh (tee + timestamped log).
exec "$(dirname "$0")/run_all_queries.sh" "$@"
