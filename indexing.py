"""Shared document chunking and Memory indexing (Session 7 + Part 2 jobs corpus)."""

from __future__ import annotations

from datetime import datetime, timezone

from memory import Memory


def chunk_text(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    stride = max(1, size - overlap)
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + size]))
        if i + size >= len(words):
            break
        i += stride
    return chunks


def index_text(
    mem: Memory,
    text: str,
    source: str,
    *,
    run_id: str,
    chunk_size: int = 400,
    overlap: int = 80,
) -> int:
    """Write chunked facts into the given Memory store. Returns chunk count."""
    if not text.strip():
        return 0
    chunks = chunk_text(text, size=chunk_size, overlap=overlap)
    for i, chunk in enumerate(chunks):
        preview = chunk[:120].replace("\n", " ")
        descriptor = f"[{source} chunk {i + 1}/{len(chunks)}] {preview}"
        mem.add_fact(
            descriptor=descriptor,
            value={
                "chunk": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source": source,
            },
            source=source,
            run_id=run_id,
        )
    return len(chunks)


def new_index_run_id() -> str:
    return f"index-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
