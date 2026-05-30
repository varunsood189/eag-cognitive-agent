"""Memory keyword read and outcome recording (no live gateway or faiss)."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from memory import Memory
from schemas import MemoryItem, ToolCall


@pytest.fixture
def mem(tmp_path: Path) -> Memory:
    return Memory(path=tmp_path / "memory.json")


@patch("memory._try_embed", return_value=None)
def test_read_keyword_overlap(_mock_embed: object, mem: Memory) -> None:
    item = MemoryItem(
        id="m1",
        kind="fact",
        keywords=["mom", "birthday", "may", "2026"],
        descriptor="Mom birthday 15 May 2026",
        value={"date": "2026-05-15", "raw": "15 May 2026"},
        source="test",
        run_id="r1",
        created_at=datetime.now(timezone.utc),
    )
    mem._save([item])  # noqa: SLF001
    hits = mem.read("When is mom's birthday?", [])
    assert len(hits) >= 1
    assert "mom" in hits[0].keywords or "birthday" in hits[0].descriptor.lower()


@patch("memory._try_embed", return_value=None)
def test_read_prefers_indexed_chunks(_mock_embed: object, mem: Memory) -> None:
    echo = MemoryItem(
        id="m0",
        kind="fact",
        keywords=["compare", "react"],
        descriptor="Comparison of ReAct and Chain-of-Thought papers",
        value={"raw": "Compare how the ReAct paper differs from CoT."},
        source="user_query",
        run_id="r1",
        created_at=datetime.now(timezone.utc),
    )
    chunk = MemoryItem(
        id="m1",
        kind="fact",
        keywords=["react", "reasoning"],
        descriptor="[workspace:papers/react.md chunk 1/3] ReAct thought steps",
        value={"chunk": "ReAct interleaves reasoning traces with actions.", "source": "workspace:papers/react.md"},
        source="workspace:papers/react.md",
        run_id="r1",
        created_at=datetime.now(timezone.utc),
    )
    mem._save([echo, chunk])  # noqa: SLF001
    hits = mem.read("ReAct intermediate reasoning", [])
    assert hits
    assert hits[0].value.get("chunk")


@patch("memory._try_embed", return_value=None)
def test_record_outcome(_mock_embed: object, mem: Memory) -> None:
    tc = ToolCall(name="web_search", arguments={"query": "tokyo"})
    item = mem.record_outcome(tc, "3 results", None, "run1", "g1")
    assert item.kind == "tool_outcome"
    assert item.value["tool"] == "web_search"
    assert len(mem._reload()) == 1  # noqa: SLF001
