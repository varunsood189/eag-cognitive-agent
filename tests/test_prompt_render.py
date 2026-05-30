"""Rendering layer tests — upstream fixes, not SYSTEM prompt rules."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from prompt_render import (
    format_memory_hits,
    summarize_action_result,
)
from schemas import MemoryItem


def _item(**kwargs) -> MemoryItem:
    base = dict(
        id="mem:test",
        kind="fact",
        keywords=[],
        descriptor="test",
        value={},
        source="test",
        run_id="r",
        created_at=datetime.now(timezone.utc),
    )
    base.update(kwargs)
    return MemoryItem(**base)


def test_format_hits_shows_raw_for_c2() -> None:
    hits = [
        _item(
            kind="fact",
            descriptor="mom's birthday remembered",
            value={"raw": "15 May 2026"},
        )
    ]
    text = format_memory_hits(hits)
    assert "15 May 2026" in text
    assert "raw:" in text


def test_format_hits_shows_chunk_not_only_descriptor() -> None:
    hits = [
        _item(
            kind="fact",
            descriptor="[workspace:papers/cot.md chunk 1/3] intro",
            value={
                "chunk": "Chain-of-thought reasoning improves multi-step math.",
                "source": "workspace:papers/cot.md",
            },
        )
    ]
    text = format_memory_hits(hits)
    assert "Chain-of-thought reasoning" in text
    assert "chunk (" in text


def test_format_hits_expands_search_knowledge_tool_outcome() -> None:
    payload = [
        {
            "descriptor": "[workspace:papers/dpo.md chunk 2/3]",
            "chunk_preview": "Preference optimization avoids reward model training.",
            "source": "workspace:papers/dpo.md",
        }
    ]
    hits = [
        _item(
            kind="tool_outcome",
            descriptor="search_knowledge(...) ->",
            value={
                "tool": "search_knowledge",
                "result_preview": json.dumps(payload),
            },
        )
    ]
    text = format_memory_hits(hits)
    assert "Preference optimization" in text
    assert "search results:" in text


def test_format_hits_shows_corpus_chunk() -> None:
    hits = [
        _item(
            kind="fact",
            descriptor="[corpus:ai_jobs/0001_JOB-IC-001 chunk 1/1] Senior ML",
            value={
                "chunk": "individual contributor modeling role salary 285000 USD",
                "source": "corpus:ai_jobs/0001_JOB-IC-001",
            },
        )
    ]
    text = format_memory_hits(hits)
    assert "individual contributor" in text
    assert "corpus:ai_jobs" in text


def test_summarize_action_result_search_knowledge() -> None:
    payload = [{"chunk_preview": "credit assignment via gradients", "descriptor": "dpo"}]
    summary = summarize_action_result("search_knowledge", json.dumps(payload))
    assert "credit assignment" in summary
