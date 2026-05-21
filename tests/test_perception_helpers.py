"""Perception safety-net helpers (no LLM)."""

from schemas import Goal, MemoryItem
from perception import _apply_history_done, _force_attach
from datetime import datetime, timezone


def test_sticky_done_via_apply_history() -> None:
    prior = [Goal(id="g1", text="a", done=True), Goal(id="g2", text="b", done=False)]
    goals = [Goal(id="g1", text="a", done=False), Goal(id="g2", text="b", done=False)]
    out = _apply_history_done(goals, [], prior)
    assert out[0].done and not out[1].done


def test_force_attach_synthesis() -> None:
    hits = [
        MemoryItem(
            id="m1",
            kind="tool_outcome",
            keywords=["fetch"],
            descriptor="fetched page",
            value={},
            artifact_id="art:abc123",
            source="mcp",
            run_id="r",
            created_at=datetime.now(timezone.utc),
        )
    ]
    assert _force_attach("Synthesise common advice from sources", hits) == "art:abc123"
