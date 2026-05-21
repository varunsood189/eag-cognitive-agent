"""Memory keyword read and outcome recording (no LLM)."""

from pathlib import Path

import pytest

from memory import Memory
from schemas import ToolCall


@pytest.fixture
def mem(tmp_path: Path) -> Memory:
    return Memory(path=tmp_path / "memory.json")


def test_read_keyword_overlap(mem: Memory) -> None:
    mem._items = []  # noqa: SLF001
    mem._loaded = True  # noqa: SLF001
    from schemas import MemoryItem
    from datetime import datetime, timezone

    mem._items.append(  # noqa: SLF001
        MemoryItem(
            id="m1",
            kind="fact",
            keywords=["mom", "birthday", "may", "2026"],
            descriptor="Mom birthday 15 May 2026",
            value={"date": "2026-05-15"},
            source="test",
            run_id="r1",
            created_at=datetime.now(timezone.utc),
        )
    )
    hits = mem.read("When is mom's birthday?", [])
    assert len(hits) >= 1
    assert "mom" in hits[0].keywords or "birthday" in hits[0].descriptor.lower()


def test_record_outcome(mem: Memory) -> None:
    tc = ToolCall(name="web_search", arguments={"query": "tokyo"})
    item = mem.record_outcome(tc, "3 results", None, "run1", "g1")
    assert item.kind == "tool_outcome"
    assert item.value["tool"] == "web_search"
    mem._load()  # noqa: SLF001
    assert len(mem._items) == 1  # noqa: SLF001
