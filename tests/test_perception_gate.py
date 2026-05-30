"""Perception prompt must not contain MCP tool names (Session 7 architectural gate)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERCEPTION_PROMPT = ROOT / "prompts" / "perception_system.txt"
MCP_SERVER = ROOT / "mcp_server.py"


def _mcp_tool_names() -> list[str]:
    text = MCP_SERVER.read_text(encoding="utf-8")
    # Match @mcp.tool() immediately followed by def tool_name(
    names = re.findall(
        r"@mcp\.tool\(\)\s*\ndef\s+([a-z][a-z0-9_]*)\s*\(",
        text,
    )
    assert names, "expected at least one @mcp.tool in mcp_server.py"
    return names


def test_perception_system_has_no_mcp_tool_names() -> None:
    prompt = PERCEPTION_PROMPT.read_text(encoding="utf-8").lower()
    violations: list[str] = []
    for name in _mcp_tool_names():
        if name.lower() in prompt:
            violations.append(name)
    assert not violations, (
        f"MCP tool names must not appear in {PERCEPTION_PROMPT.name}: {violations}. "
        "Perception speaks intent only; Decision maps goals to tools via docstrings."
    )


def test_decision_system_documents_index_directory() -> None:
    """Bulk index intent should be documented for Decision, not Perception."""
    decision = (ROOT / "prompts" / "decision_system.txt").read_text(encoding="utf-8")
    assert "index_directory" in decision


def test_perception_bulk_ingest_one_folder_goal() -> None:
    text = PERCEPTION_PROMPT.read_text(encoding="utf-8").lower()
    assert "one goal" in text or "one goal to make" in text
    assert "every file under" in text or "whole folder" in text
    assert "index_directory" not in text
