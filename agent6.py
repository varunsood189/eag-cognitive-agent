"""
agent6.py — Session 6 four-role cognitive loop.

Memory → Perception → Decision → Action, until Perception marks all goals done.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import action
import decision
import perception
from artifacts import ArtifactStore
from gateway import ensure_gateway
from memory import memory
from schemas import Goal

MAX_ITERATIONS = 24
SERVER_PATH = Path(__file__).resolve().parent / "mcp_server.py"
artifacts = ArtifactStore()


def mcp_tool_to_gateway(t) -> dict:
    return {
        "name": t.name,
        "description": t.description or "",
        "input_schema": t.inputSchema or {"type": "object", "properties": {}},
    }


@asynccontextmanager
async def mcp_session():
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def final_answer_from(history: list[dict]) -> str:
    answers = [h["text"] for h in history if h.get("kind") == "answer" and h.get("text")]
    if answers:
        return answers[-1]
    actions = [h for h in history if h.get("kind") == "action"]
    if actions:
        return actions[-1].get("result_descriptor", "Task completed (see action log).")
    return "No answer produced."


def _log(msg: str) -> None:
    print(msg, flush=True)


async def run(query: str, *, verbose: bool = True) -> str:
    ensure_gateway()
    run_id = uuid.uuid4().hex[:8]
    history: list[dict] = []
    prior_goals: list[Goal] = []

    if verbose:
        _log(f"\n{'=' * 60}\nRUN {run_id}\nQUERY: {query}\n{'=' * 60}")

    memory.remember(query, source="user_query", run_id=run_id)

    async with mcp_session() as session:
        mcp_tools_raw = (await session.list_tools()).tools
        tools = [mcp_tool_to_gateway(t) for t in mcp_tools_raw]
        if verbose:
            _log(f"[mcp] tools: {[t['name'] for t in tools]}")

        for it in range(1, MAX_ITERATIONS + 1):
            if verbose:
                _log(f"\n─── iter {it} ───")

            hits = memory.read(query, history)
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
            memory.record_outcome(tc, result_text, art_id, run_id, goal.id)

            if verbose:
                _log(f"[action]      → {result_text[:300]}")

            history.append(
                {
                    "iter": it,
                    "kind": "action",
                    "goal_id": goal.id,
                    "tool": tc.name,
                    "arguments": tc.arguments,
                    "result_descriptor": result_text[:300],
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
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Session 6 cognitive agent")
    parser.add_argument("--query", "-q", help="User query text")
    parser.add_argument("--preset", choices=list(QUERIES.keys()), help="Run a target query preset")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.preset:
        text = QUERIES[args.preset]
    elif args.query:
        text = args.query
    else:
        parser.error("Provide --query or --preset")

    result = asyncio.run(run(text, verbose=not args.quiet))
    print(result)


if __name__ == "__main__":
    main()
