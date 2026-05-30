"""Pydantic contracts for Session 6 role boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MemoryItem(BaseModel):
    id: str
    kind: Literal["fact", "preference", "tool_outcome", "scratchpad"]
    keywords: list[str]
    descriptor: str
    value: dict
    artifact_id: str | None = None
    embedding: list[float] | None = None
    source: str
    run_id: str
    goal_id: str | None = None
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Artifact(BaseModel):
    id: str
    content_type: str
    size_bytes: int
    source: str
    descriptor: str


class Goal(BaseModel):
    id: str
    text: str
    done: bool = False
    attach_artifact_id: str | None = None


class Observation(BaseModel):
    goals: list[Goal] = Field(default_factory=list)

    @property
    def all_done(self) -> bool:
        return bool(self.goals) and all(g.done for g in self.goals)

    def next_unfinished(self) -> Goal | None:
        for g in self.goals:
            if not g.done:
                return g
        return None


class ToolCall(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)


class DecisionOutput(BaseModel):
    answer: str | None = None
    tool_call: ToolCall | None = None

    @model_validator(mode="after")
    def exactly_one_output(self) -> DecisionOutput:
        has_answer = bool(self.answer and self.answer.strip())
        has_tool = self.tool_call is not None
        if has_answer == has_tool:
            raise ValueError("DecisionOutput must have exactly one of answer or tool_call")
        return self

    @property
    def is_answer(self) -> bool:
        return bool(self.answer and self.answer.strip())


class PerceptionGoalDraft(BaseModel):
    """LLM-facing shape: positional goals, no string artifact ids."""

    text: str
    done: bool = False
    artifact_index: int | None = None


class PerceptionLLMOutput(BaseModel):
    goals: list[PerceptionGoalDraft] = Field(default_factory=list)


class MemoryClassification(BaseModel):
    kind: Literal["fact", "preference", "tool_outcome", "scratchpad"]
    keywords: list[str]
    descriptor: str
    value: dict
    confidence: float = 1.0
