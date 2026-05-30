"""
agent7.py — Session 7 four-role cognitive loop (FAISS vector memory).

Memory → Perception → Decision → Action, until Perception marks all goals done.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import action
import decision
import perception
from history_utils import final_answer_from
from jobs_rag_queries import AGENT_PRESETS
from prompt_render import summarize_action_result
from artifacts import ArtifactStore
from gateway import ensure_gateway
import memory as memory_mod
from schemas import Goal

MAX_ITERATIONS = 24
BASE_DIR = Path(__file__).resolve().parent
SERVER_PATH = BASE_DIR / "mcp_server.py"
artifacts = ArtifactStore()


JOBS_STATE_DIR = "state_jobs"


def _ensure_papers_in_workspace() -> None:
    src = BASE_DIR / "papers"
    if not src.is_dir():
        return
    dest = BASE_DIR / "workspace" / "papers"
    dest.mkdir(parents=True, exist_ok=True)
    for md in src.glob("*.md"):
        shutil.copy2(md, dest / md.name)


def _ensure_jobs_in_workspace() -> None:
    src = BASE_DIR / "corpus" / "ai_jobs" / "items"
    if not src.is_dir():
        return
    dest = BASE_DIR / "workspace" / "ai_jobs"
    dest.mkdir(parents=True, exist_ok=True)
    for md in src.glob("*.md"):
        shutil.copy2(md, dest / md.name)


def _is_jobs_preset(preset: str | None) -> bool:
    return preset is not None and preset.startswith("j")


def mcp_tool_to_gateway(t) -> dict:
    return {
        "name": t.name,
        "description": t.description or "",
        "input_schema": t.inputSchema or {"type": "object", "properties": {}},
    }


@asynccontextmanager
async def mcp_session(*, state_dir: str | None = None):
    env = dict(os.environ)
    if state_dir:
        env["EAG_STATE_DIR"] = state_dir
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _log(msg: str) -> None:
    print(msg, flush=True)


async def run(
    query: str,
    *,
    verbose: bool = True,
    state_dir: str | None = None,
) -> str:
    _ensure_papers_in_workspace()
    if state_dir:
        memory_mod.rebind(state_dir)
        _ensure_jobs_in_workspace()
    else:
        memory_mod.rebind("state")
    ensure_gateway()
    run_id = uuid.uuid4().hex[:8]
    history: list[dict] = []
    prior_goals: list[Goal] = []

    if verbose:
        _log(f"\n{'=' * 60}\nRUN {run_id}\nQUERY: {query}\n{'=' * 60}")

    memory_mod.memory.remember(query, source="user_query", run_id=run_id)

    async with mcp_session(state_dir=state_dir) as session:
        mcp_tools_raw = (await session.list_tools()).tools
        tools = [mcp_tool_to_gateway(t) for t in mcp_tools_raw]
        if verbose:
            _log(f"[mcp] tools: {[t['name'] for t in tools]}")

        for it in range(1, MAX_ITERATIONS + 1):
            if verbose:
                _log(f"\n─── iter {it} ───")

            hits = memory_mod.memory.read(query, history)
            if verbose:
                _log(f"[memory.read] {len(hits)} hits")

            obs = perception.observe(query, hits, history, prior_goals, run_id)
            prior_goals = obs.goals

            if verbose:
                for g in obs.goals:
                    att = f" attach={g.attach_artifact_id}" if g.attach_artifact_id else ""
                    status = "done" if g.done else "open"
                    _log(f"[perception]  [{status}] {g.text}{att}")

            if obs.all_done:
                if verbose:
                    _log("[done] all goals satisfied")
                break

            goal = obs.next_unfinished()
            if goal is None:
                break

            attached: list[tuple[str, bytes]] = []
            if goal.attach_artifact_id and artifacts.exists(goal.attach_artifact_id):
                blob = artifacts.get_bytes(goal.attach_artifact_id)
                attached.append((goal.attach_artifact_id, blob))
                if verbose:
                    _log(f"[attach] {goal.attach_artifact_id} ({len(blob)} bytes)")

            out = decision.next_step(goal, hits, attached, history, tools)

            if out.is_answer:
                if verbose:
                    _log(f"[decision]  ANSWER: {out.answer[:300]}...")
                history.append(
                    {"iter": it, "kind": "answer", "goal_id": goal.id, "text": out.answer}
                )
                continue

            tc = out.tool_call
            assert tc is not None
            if verbose:
                _log(f"[decision]  TOOL_CALL: {tc.name}({json.dumps(tc.arguments)})")

            result_text, art_id = await action.execute(session, tc)
            memory_mod.memory.record_outcome(tc, result_text, art_id, run_id, goal.id)

            if verbose:
                _log(f"[action]      → {result_text[:300]}")

            history.append(
                {
                    "iter": it,
                    "kind": "action",
                    "goal_id": goal.id,
                    "tool": tc.name,
                    "arguments": tc.arguments,
                    "result_summary": summarize_action_result(tc.name, result_text),
                    "result_descriptor": summarize_action_result(tc.name, result_text),
                    "artifact_id": art_id,
                }
            )
        else:
            if verbose:
                _log(f"[warn] exceeded MAX_ITERATIONS={MAX_ITERATIONS}")

    final = final_answer_from(history)
    if verbose:
        _log(f"\nFINAL:\n{final}\n")
    return final


QUERIES = {
    "a": (
        "Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his "
        "birth date, death date, and three key contributions to information theory."
    ),
    "b": (
        "Find 3 family-friendly things to do in Tokyo this weekend. "
        "Check Saturday's weather forecast there and tell me which one is most appropriate."
    ),
    "c1": (
        "My mom's birthday is 15 May 2026. Remember that and give me a calendar "
        "reminder for two weeks before and on the day."
    ),
    "c2": "When is mom's birthday?",
    "d": (
        "Search for 'Python asyncio best practices', read the top 3 results, "
        "and give me a short numbered list of the advice they agree on."
    ),
    "e": (
        "Index the file papers/attention.md and tell me what the three key "
        "contributions of the Transformer architecture are according to this paper."
    ),
    "f1": (
        "Index every .md file under papers/. Confirm how many chunks were indexed in total."
    ),
    "f2": (
        "Across the papers I have indexed, what do they say about "
        "chain-of-thought reasoning?"
    ),
    "g": (
        "Across these papers, how do they handle the credit assignment problem?"
    ),
    "h": (
        "Compare how the ReAct paper and the Chain-of-Thought paper differ "
        "in their treatment of intermediate reasoning."
    ),
}
QUERIES.update(AGENT_PRESETS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Session 7 cognitive agent")
    parser.add_argument("--query", "-q", help="User query text")
    parser.add_argument("--preset", choices=sorted(QUERIES.keys()), help="Run a target query preset")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.preset:
        text = QUERIES[args.preset]
    elif args.query:
        text = args.query
    else:
        parser.error("Provide --query or --preset")

    state_dir = JOBS_STATE_DIR if _is_jobs_preset(args.preset) else None
    result = asyncio.run(run(text, verbose=not args.quiet, state_dir=state_dir))
    # Verbose runs already print FINAL inside run(); avoid printing twice.
    if args.quiet:
        print(result)


if __name__ == "__main__":
    main()
