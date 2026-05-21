"""Pydantic boundary tests."""

import pytest

from schemas import DecisionOutput, ToolCall


def test_decision_output_xor() -> None:
    DecisionOutput(answer="done", tool_call=None)
    DecisionOutput(answer=None, tool_call=ToolCall(name="x", arguments={}))
    with pytest.raises(ValueError):
        DecisionOutput(answer="a", tool_call=ToolCall(name="x", arguments={}))
    with pytest.raises(ValueError):
        DecisionOutput(answer=None, tool_call=None)
