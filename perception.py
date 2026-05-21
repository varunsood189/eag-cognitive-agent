"""Perception — goal decomposition, done tracking, artifact attachment."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from gateway import gateway_chat, parse_structured, response_format_from_model
from schemas import Goal, MemoryItem, Observation, PerceptionLLMOutput

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "perception_system.txt"
SYNTHESIS_KEYWORDS = frozenset(
    "synthesise synthesize extract list compare decide choose recommend summarize summary".split()
)
URL_RE = re.compile(r"https?://[^\s\)\]\"']+")


def _system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _first_url(query: str) -> str | None:
    m = URL_RE.search(query)
    if not m:
        return None
    return m.group(0).rstrip(".,;)")


def _seed_url_fetch_goals(query: str) -> Observation | None:
    """Query A pattern: exactly two goals — fetch once, then extract."""
    url = _first_url(query)
    if not url:
        return None
    return Observation(
        goals=[
            Goal(id="g1:seed", text=f"Fetch {url}", done=False),
            Goal(
                id="g2:seed",
                text="Extract the facts requested in the user query from the fetched page",
                done=False,
            ),
        ]
    )


def _format_hits(hits: list[MemoryItem]) -> tuple[str, list[str | None]]:
    artifact_by_index: list[str | None] = []
    lines: list[str] = []
    for i, h in enumerate(hits):
        art_note = ""
        if h.artifact_id:
            artifact_by_index.append(h.artifact_id)
            art_note = f" artifact_index={len(artifact_by_index) - 1}"
        else:
            artifact_by_index.append(None)
        lines.append(
            f"[{i}] kind={h.kind} descriptor={h.descriptor!r} keywords={h.keywords}{art_note}"
        )
    return "\n".join(lines) if lines else "(no hits)", artifact_by_index


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(empty)"
    return json.dumps(history[-12:], ensure_ascii=True, indent=2)


def _format_prior(goals: list[Goal]) -> str:
    if not goals:
        return "(empty — decompose the user query)"
    return json.dumps(
        [{"id": g.id, "text": g.text, "done": g.done, "attach": g.attach_artifact_id} for g in goals],
        indent=2,
    )


def _action_ok(descriptor: str) -> bool:
    d = descriptor or ""
    return not d.startswith('{"error"') and not d.startswith("ERROR:")


def _history_satisfies_goal(goal: Goal, history: list[dict]) -> bool:
    """Done only from run history — never from the Perception LLM's done flag."""
    text_l = goal.text.lower()
    for ev in history:
        if ev.get("goal_id") != goal.id:
            continue
        if ev.get("kind") == "answer" and (ev.get("text") or "").strip():
            return True
        if ev.get("kind") != "action":
            continue
        tool = ev.get("tool", "")
        desc = ev.get("result_descriptor", "")

        if tool == "web_search" and _action_ok(desc):
            if any(
                k in text_l
                for k in ("find", "search", "list", "things to do", "activities", "family")
            ):
                return True

        if tool == "fetch_url" and _action_ok(desc):
            if any(k in text_l for k in ("fetch", "weather", "forecast")):
                return True

        if tool in ("create_file", "update_file", "edit_file", "list_dir", "read_file"):
            if _action_ok(desc):
                return True
    return False


def _apply_history_done(
    goals: list[Goal], history: list[dict], prior_goals: list[Goal]
) -> list[Goal]:
    if not history:
        out: list[Goal] = []
        for i, g in enumerate(goals):
            sticky = prior_goals[i].done if i < len(prior_goals) else False
            out.append(g.model_copy(update={"done": sticky}))
        return out
    out: list[Goal] = []
    for i, g in enumerate(goals):
        sticky = prior_goals[i].done if i < len(prior_goals) else False
        out.append(
            g.model_copy(update={"done": sticky or _history_satisfies_goal(g, history)})
        )
    return out


def _force_attach(goal_text: str, hits: list[MemoryItem]) -> str | None:
    lower = goal_text.lower()
    attach_keywords = SYNTHESIS_KEYWORDS | frozenset(
        ("appropriate", "which one", "determine", "decide", "choose", "recommend")
    )
    if not any(k in lower for k in attach_keywords):
        return None
    for h in reversed(hits):
        if h.artifact_id:
            return h.artifact_id
    return None


def observe(
    query: str,
    hits: list[MemoryItem],
    history: list[dict],
    prior_goals: list[Goal],
    run_id: str,
) -> Observation:
    if not prior_goals and not history:
        seeded = _seed_url_fetch_goals(query)
        if seeded:
            return seeded

    hits_block, artifact_index_map = _format_hits(hits)
    user = (
        f"USER QUERY:\n{query}\n\n"
        f"RUN ID: {run_id}\n\n"
        f"MEMORY HITS:\n{hits_block}\n\n"
        f"RUN HISTORY:\n{_format_history(history)}\n\n"
        f"PRIOR GOALS:\n{_format_prior(prior_goals)}\n"
    )

    reply = gateway_chat(
        prompt=user,
        system=_system_prompt(),
        auto_route="perception",
        provider="g",
        temperature=1.0,
        max_tokens=2048,
        response_format=response_format_from_model(PerceptionLLMOutput),
    )
    llm_out = parse_structured(reply, PerceptionLLMOutput)

    goals: list[Goal] = []
    for i, draft in enumerate(llm_out.goals):
        gid = prior_goals[i].id if i < len(prior_goals) else f"g{i + 1}:{uuid.uuid4().hex[:6]}"
        attach: str | None = None
        if draft.artifact_index is not None and 0 <= draft.artifact_index < len(artifact_index_map):
            attach = artifact_index_map[draft.artifact_index]
        goals.append(
            Goal(
                id=gid,
                text=draft.text,
                done=False,
                attach_artifact_id=attach,
            )
        )

    goals = _apply_history_done(goals, history, prior_goals)

    open_idx = next((i for i, g in enumerate(goals) if not g.done), None)
    if open_idx is not None and not goals[open_idx].attach_artifact_id:
        forced = _force_attach(goals[open_idx].text, hits)
        if forced:
            goals[open_idx] = goals[open_idx].model_copy(update={"attach_artifact_id": forced})

    return Observation(goals=goals)
