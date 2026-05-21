"""Perception done flags come from history, not LLM."""

from schemas import Goal
from perception import _history_satisfies_goal


def test_web_search_satisfies_find_goal() -> None:
    goal = Goal(id="g1", text="Find 3 family-friendly things to do in Tokyo", done=False)
    history = [
        {
            "goal_id": "g1",
            "kind": "action",
            "tool": "web_search",
            "result_descriptor": '[{"title": "Ueno Zoo", "url": "http://x"}]',
        }
    ]
    assert _history_satisfies_goal(goal, history)


def test_error_action_does_not_satisfy() -> None:
    goal = Goal(id="g1", text="Find 3 activities", done=False)
    history = [
        {
            "goal_id": "g1",
            "kind": "action",
            "tool": "read_file",
            "result_descriptor": "ERROR: artifact handles invalid",
        }
    ]
    assert not _history_satisfies_goal(goal, history)
