"""Decision — one goal, one LLM call, answer or single tool."""

from __future__ import annotations

import json
from pathlib import Path

from gateway import gateway_chat
from prompt_render import format_memory_hits
from schemas import DecisionOutput, Goal, MemoryItem, ToolCall

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "decision_system.txt"

# Keep Decision prompts under gateway HUGE-tier guard (~8k tokens).
MAX_ATTACHED_CHARS = 24_000
_EXCERPT_KEYWORDS = (
    "born",
    "birth",
    "died",
    "death",
    "1916",
    "2001",
    "april",
    "february",
    "contribution",
    "information theory",
    "communication",
    "entropy",
    "shannon",
)


def _system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _excerpt_artifact(text: str) -> str:
    """Shrink large page artifacts so Decision fits gateway context limits."""
    if len(text) <= MAX_ATTACHED_CHARS:
        return text

    sections: list[str] = [text[:12_000]]
    lower = text.lower()
    for kw in _EXCERPT_KEYWORDS:
        idx = 0
        while True:
            idx = lower.find(kw, idx)
            if idx < 0:
                break
            start = max(0, idx - 500)
            end = min(len(text), idx + 1500)
            snippet = text[start:end]
            if snippet not in sections:
                sections.append(f"\n--- excerpt near '{kw}' ---\n{snippet}")
            idx += len(kw)

    joined = "\n".join(sections)
    if len(joined) > MAX_ATTACHED_CHARS:
        joined = joined[:MAX_ATTACHED_CHARS]
    return joined + f"\n\n[Note: full artifact was {len(text)} chars; excerpt shown for extraction.]"


def _run_context(goal: Goal, history: list[dict], hits: list[MemoryItem]) -> str:
    """Runtime facts only — policy lives in prompts/decision_system.txt."""
    parts: list[str] = []
    fetched = [
        ev.get("arguments", {}).get("url")
        for ev in history
        if ev.get("kind") == "action" and ev.get("tool") == "fetch_url"
    ]
    parts.append(
        f"URLs already fetched this run: {fetched}" if fetched else "URLs already fetched this run: (none)"
    )

    goal_l = goal.text.lower()
    searches = [
        ev
        for ev in history
        if ev.get("kind") == "action" and ev.get("tool") == "search_knowledge"
    ]
    if len(searches) >= 2 and any(
        k in goal_l for k in ("compare", "contrast", "synthes", "summar", "answer")
    ):
        parts.append(
            "RECENT HISTORY already has multiple search_knowledge results; "
            "respond with a plain-text answer from MEMORY HITS and those results."
        )

    chunk_hits = 0
    for h in hits:
        val = h.value or {}
        if val.get("chunk") or "chunk:" in (h.descriptor or ""):
            chunk_hits += 1
    if chunk_hits >= 2 and any(k in goal_l for k in ("compare", "contrast")):
        parts.append(
            "MEMORY HITS already include indexed paper chunks; write the comparison in plain text."
        )

    return "\n".join(parts)


def _format_attached(attached: list[tuple[str, bytes]]) -> str:
    if not attached:
        return "(none)"
    parts = []
    for art_id, blob in attached:
        try:
            text = blob.decode("utf-8", errors="replace")
        except Exception:
            text = repr(blob[:2000])
        parts.append(
            f"=== {art_id} ({len(blob)} bytes, excerpt below) ===\n{_excerpt_artifact(text)}"
        )
    return "\n\n".join(parts)


def next_step(
    goal: Goal,
    hits: list[MemoryItem],
    attached: list[tuple[str, bytes]],
    history: list[dict],
    mcp_tools: list[dict],
) -> DecisionOutput:
    user = (
        f"CURRENT GOAL (only goal you may work on):\n{goal.text}\n\n"
        f"GOAL ID: {goal.id}\n\n"
        f"RUN CONTEXT:\n{_run_context(goal, history, hits)}\n\n"
        f"MEMORY HITS:\n{format_memory_hits(hits)}\n\n"
        f"ATTACHED ARTIFACTS:\n{_format_attached(attached)}\n\n"
        f"RECENT HISTORY:\n{json.dumps(history[-8:], ensure_ascii=True, indent=2)}\n"
    )

    # Large attached pages need Gemini (long context); router HUGE tier otherwise 503s.
    chat_kwargs: dict = {
        "messages": [{"role": "user", "content": user}],
        "system": _system_prompt(),
        "auto_route": "decision",
        "tools": mcp_tools,
        "tool_choice": "auto",
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    if attached:
        chat_kwargs["provider"] = "g"
        chat_kwargs["tools"] = None
        chat_kwargs["tool_choice"] = None

    reply = gateway_chat(**chat_kwargs)

    tool_calls = reply.get("tool_calls") or []
    if tool_calls:
        tc = tool_calls[0]
        return DecisionOutput(
            tool_call=ToolCall(
                name=tc["name"],
                arguments=tc.get("arguments") or {},
            )
        )

    text = (reply.get("text") or "").strip()
    if not text:
        raise ValueError("Decision returned neither tool nor text")
    return DecisionOutput(answer=text)
