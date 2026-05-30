#!/usr/bin/env python3
"""
Part 2 — AI Jobs Market RAG CLI.

Index:  python scripts/index_ai_jobs_corpus.py
Query:  python jobs_rag.py --preset q1
         python jobs_rag.py --query "..." --no-index
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from gateway import ensure_gateway, gateway_chat
from jobs_rag_queries import CUSTOM_QUERIES
from memory import Memory
from prompt_render import format_memory_hits

ROOT = Path(__file__).resolve().parent
STATE_JOBS = ROOT / "state_jobs"
TRACES_DIR = ROOT / "docs" / "traces"

SYSTEM = """You answer questions about AI job postings using ONLY the retrieved job records below.
If the records do not contain enough information, say clearly that you cannot answer from the corpus.
Do not invent salaries, employers, or locations. Cite role titles and countries when relevant."""


def _jobs_memory(*, use_index: bool) -> Memory:
    path = STATE_JOBS / "memory.json"
    if not use_index:
        empty_dir = ROOT / "state_jobs_empty"
        if empty_dir.exists():
            shutil.rmtree(empty_dir)
        empty_dir.mkdir(parents=True)
        return Memory(empty_dir / "memory.json")
    if not path.is_file():
        raise FileNotFoundError(
            "Jobs index not found. Run: python scripts/index_ai_jobs_corpus.py"
        )
    return Memory(path)


def answer(query: str, *, use_index: bool, top_k: int = 8) -> tuple[str, str]:
    """Returns (answer_text, hits_block_for_trace)."""
    mem = _jobs_memory(use_index=use_index)
    hits = mem.read(query, [], kinds=["fact"], top_k=top_k)
    hits_block = format_memory_hits(hits)

    if not hits:
        return (
            "I cannot answer from the job salary knowledge base because no indexed records "
            "were retrieved for this question.",
            hits_block,
        )

    ensure_gateway()
    user = f"USER QUESTION:\n{query}\n\nRETRIEVED JOB RECORDS:\n{hits_block}\n"
    reply = gateway_chat(
        prompt=user,
        system=SYSTEM,
        auto_route="decision",
        provider="g",
        temperature=0.2,
        max_tokens=2048,
    )
    text = (reply.get("text") or "").strip()
    if not text:
        raise ValueError("Gateway returned empty answer")
    return text, hits_block


def _write_trace(path: Path, query: str, use_index: bool, answer_text: str, hits_block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "with-index" if use_index else "no-index"
    header = (
        f"# Custom query trace ({mode})\n"
        f"# {datetime.now(timezone.utc).isoformat()}\n\n"
        f"QUERY:\n{query}\n\n"
        f"MEMORY HITS:\n{hits_block}\n\n"
        f"ANSWER:\n{answer_text}\n"
    )
    path.write_text(header, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Jobs Market RAG (Part 2)")
    parser.add_argument("--query", "-q", help="Question text")
    parser.add_argument("--preset", choices=list(CUSTOM_QUERIES.keys()), help="q1–q5")
    parser.add_argument("--no-index", action="store_true", help="Query without FAISS corpus")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument(
        "--trace-out",
        type=Path,
        help="Write trace file (e.g. docs/traces/custom-q1-with-index.txt)",
    )
    parser.add_argument(
        "--write-traces",
        action="store_true",
        help="Write both with-index and no-index traces for --preset",
    )
    args = parser.parse_args()

    if args.preset:
        query = CUSTOM_QUERIES[args.preset]
    elif args.query:
        query = args.query
    else:
        parser.error("Provide --query or --preset")

    if args.write_traces:
        if not args.preset:
            parser.error("--write-traces requires --preset")
        for use_index in (True, False):
            suffix = "with-index" if use_index else "no-index"
            out = TRACES_DIR / f"custom-{args.preset}-{suffix}.txt"
            text, hits = answer(query, use_index=use_index, top_k=args.top_k)
            _write_trace(out, query, use_index, text, hits)
            print(f"Wrote {out}")
        return

    text, hits = answer(query, use_index=not args.no_index, top_k=args.top_k)
    print(text)
    if args.trace_out:
        _write_trace(args.trace_out, query, not args.no_index, text, hits)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
