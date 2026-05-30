#!/usr/bin/env python3
"""Index corpus/ai_jobs/items into state_jobs/ (isolated from course state/)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ITEMS_DIR = ROOT / "corpus" / "ai_jobs" / "items"
WORKSPACE_JOBS = ROOT / "workspace" / "ai_jobs"
STATE_JOBS = ROOT / "state_jobs"


def main() -> None:
    parser = argparse.ArgumentParser(description="Index AI jobs corpus into state_jobs/")
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar (plain logs only)",
    )
    args = parser.parse_args()

    if not ITEMS_DIR.is_dir() or not any(ITEMS_DIR.glob("*.md")):
        raise SystemExit("Run scripts/build_ai_jobs_corpus.py first.")

    md_files = sorted(ITEMS_DIR.glob("*.md"))
    total_files = len(md_files)
    tqdm.write(
        f"Indexing {total_files} corpus files → {STATE_JOBS.relative_to(ROOT)}/"
    )
    tqdm.write(
        "Requires LLM Gateway V7 on :8107 with Ollama nomic-embed-text (~10–20 min)."
    )

    if STATE_JOBS.exists():
        shutil.rmtree(STATE_JOBS)
    STATE_JOBS.mkdir(parents=True)

    WORKSPACE_JOBS.mkdir(parents=True, exist_ok=True)
    for md in md_files:
        shutil.copy2(md, WORKSPACE_JOBS / md.name)

    from indexing import index_text, new_index_run_id
    from memory import Memory

    mem = Memory(STATE_JOBS / "memory.json")
    mem.begin_batch()
    run_id = new_index_run_id()
    total_chunks = 0
    files_indexed = 0
    t0 = time.monotonic()

    workspace_files = sorted(WORKSPACE_JOBS.glob("*.md"))
    iterator = workspace_files
    if not args.no_progress:
        iterator = tqdm(
            workspace_files,
            desc="Indexing jobs",
            unit="file",
            dynamic_ncols=True,
        )

    try:
        for md in iterator:
            text = md.read_text(encoding="utf-8")
            source = f"corpus:ai_jobs/{md.stem}"
            n = index_text(mem, text, source, run_id=run_id)
            total_chunks += n
            files_indexed += 1
            if not args.no_progress and hasattr(iterator, "set_postfix"):
                iterator.set_postfix(chunks=total_chunks, refresh=False)
    finally:
        tqdm.write("Writing memory.json and FAISS index…")
        mem.commit_batch()

    elapsed = time.monotonic() - t0
    summary = {
        "files_indexed": files_indexed,
        "total_chunks_indexed": total_chunks,
        "state_dir": str(STATE_JOBS.relative_to(ROOT)),
        "elapsed_seconds": round(elapsed, 1),
    }
    tqdm.write(json.dumps(summary, indent=2))
    if files_indexed < 50:
        raise SystemExit(f"Expected at least 50 files; indexed {files_indexed}")
    if total_chunks < 50:
        raise SystemExit(f"Expected at least 50 chunks; got {total_chunks}")


if __name__ == "__main__":
    main()
