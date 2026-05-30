"""Run-history helpers (no MCP imports)."""

from __future__ import annotations


def is_substantive_answer(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 40:
        return False
    if t.startswith("[artifact") or ("preview:" in t[:80].lower() and len(t) < 200):
        return False
    return True


def final_answer_from(history: list[dict]) -> str:
    answers = [
        h["text"]
        for h in history
        if h.get("kind") == "answer" and is_substantive_answer(h.get("text", ""))
    ]
    if answers:
        return answers[-1]
    actions = [h for h in history if h.get("kind") == "action"]
    if actions:
        return actions[-1].get("result_descriptor", "Task completed (see action log).")
    return "No answer produced."
