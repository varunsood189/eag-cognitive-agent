#!/usr/bin/env bash
# Session 7 architectural gate: Perception SYSTEM must not name MCP tools.
# Decision learns tools from MCP docstrings + prompts/decision_system.txt.
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "$0")/env.sh"

PERCEPTION_PROMPT="prompts/perception_system.txt"
MCP_SERVER="mcp_server.py"

if [[ ! -f "$PERCEPTION_PROMPT" ]]; then
  echo "ERROR: missing $PERCEPTION_PROMPT" >&2
  exit 1
fi

mapfile -t TOOLS < <(
  python3 -c "
import re
from pathlib import Path
text = Path('$MCP_SERVER').read_text()
for name in re.findall(r'@mcp\.tool\(\)\s*\ndef\s+([a-z][a-z0-9_]*)\s*\(', text):
    print(name)
"
)

if ((${#TOOLS[@]} == 0)); then
  echo "ERROR: no @mcp.tool handlers found in $MCP_SERVER" >&2
  exit 1
fi

PATTERN=$(IFS='|'; echo "${TOOLS[*]}")
if grep -E "$PATTERN" "$PERCEPTION_PROMPT" >/dev/null; then
  echo "FAIL: MCP tool names found in $PERCEPTION_PROMPT (Perception must use intent only):" >&2
  grep -nE "$PATTERN" "$PERCEPTION_PROMPT" >&2
  exit 1
fi

echo "PASS: perception gate — no MCP tool names in $PERCEPTION_PROMPT"
echo "      checked ${#TOOLS[@]} tools: ${TOOLS[*]}"
