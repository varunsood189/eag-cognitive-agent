"""Seeded goals when indexed paper chunks are already in memory."""

from __future__ import annotations

from perception import _seed_indexed_corpus_goals, _seed_url_fetch_goals
from schemas import MemoryItem


def _paper_hit(descriptor: str = "[workspace:papers/react.md]") -> MemoryItem:
    return MemoryItem(
        id="m1",
        kind="tool_outcome",
        keywords=["react"],
        descriptor=descriptor,
        value={"chunk": "ReAct uses thought-action loops."},
        source="workspace:papers/react.md",
        run_id="r1",
    )


def test_url_seed_takes_priority_over_corpus_seed() -> None:
    query = "Fetch https://example.com and summarize it"
    assert _seed_url_fetch_goals(query) is not None
    assert _seed_indexed_corpus_goals(query, [_paper_hit()]) is None


def test_compare_query_seeds_three_rag_goals() -> None:
    query = (
        "Compare how the ReAct paper and the Chain-of-Thought paper differ "
        "in their treatment of intermediate reasoning."
    )
    obs = _seed_indexed_corpus_goals(query, [_paper_hit()])
    assert obs is not None
    assert len(obs.goals) == 3
    assert all("knowledge base" in g.text.lower() for g in obs.goals[:2])
    assert "compare" in obs.goals[2].text.lower()


def test_f2_style_query_seeds_two_goals() -> None:
    query = "Across the papers I have indexed, what do they say about chain-of-thought?"
    obs = _seed_indexed_corpus_goals(query, [_paper_hit()])
    assert obs is not None
    assert len(obs.goals) == 2


def test_indexing_run_not_seeded() -> None:
    query = "Index every .md file under papers/. Confirm how many chunks were indexed."
    assert _seed_indexed_corpus_goals(query, [_paper_hit()]) is None
