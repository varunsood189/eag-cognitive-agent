"""Render typed memory/history objects into prompt text (upstream of Perception/Decision)."""

from __future__ import annotations

import json
from typing import Any

from schemas import MemoryItem

# Decision must see enough chunk text to answer RAG goals without re-searching.
MAX_CHUNK_CHARS = 900
MAX_RAW_CHARS = 400
MAX_TOOL_PREVIEW_CHARS = 2_400
MAX_HISTORY_TOOL_CHARS = 1_800


def _expand_search_knowledge_preview(preview: str) -> str:
    try:
        rows = json.loads(preview)
    except json.JSONDecodeError:
        return preview
    if not isinstance(rows, list):
        return preview
    parts: list[str] = []
    for row in rows[:6]:
        if not isinstance(row, dict):
            continue
        desc = (row.get("descriptor") or "")[:120]
        chunk = (row.get("chunk_preview") or "").strip()
        src = row.get("source") or ""
        if chunk:
            parts.append(f"  • {desc}\n    text: {chunk}")
        elif desc:
            parts.append(f"  • {desc} ({src})")
    return "\n".join(parts) if parts else preview


def _value_body(val: dict[str, Any], *, max_chunk: int, max_raw: int) -> list[str]:
    lines: list[str] = []
    raw = val.get("raw")
    if isinstance(raw, str) and raw.strip():
        text = raw.strip().replace("\n", " ")
        more = "…" if len(text) > max_raw else ""
        lines.append(f"      raw: {text[:max_raw]}{more}")

    chunk = val.get("chunk")
    if isinstance(chunk, str) and chunk.strip():
        src = val.get("source") or ""
        text = chunk.replace("\n", " ")
        more = "…" if len(chunk) > max_chunk else ""
        label = f"chunk ({src})" if src else "chunk"
        lines.append(f"      {label}: {text[:max_chunk]}{more}")

    preview = val.get("result_preview")
    if isinstance(preview, str) and preview.strip():
        tool = val.get("tool")
        if tool == "search_knowledge":
            expanded = _expand_search_knowledge_preview(preview)
            if len(expanded) > MAX_TOOL_PREVIEW_CHARS:
                expanded = expanded[:MAX_TOOL_PREVIEW_CHARS] + "…"
            lines.append(f"      search results:\n{expanded}")
        else:
            p = preview.replace("\n", " ")[:MAX_TOOL_PREVIEW_CHARS]
            more = "…" if len(preview) > MAX_TOOL_PREVIEW_CHARS else ""
            lines.append(f"      result: {p}{more}")

    return lines


def format_memory_hits(
    hits: list[MemoryItem],
    *,
    max_items: int = 10,
    max_chunk: int = MAX_CHUNK_CHARS,
    max_raw: int = MAX_RAW_CHARS,
) -> str:
    if not hits:
        return "(none)"
    lines: list[str] = []
    for i, h in enumerate(hits[:max_items]):
        art = f" artifact={h.artifact_id}" if h.artifact_id else ""
        lines.append(f"[{i}] {h.kind}: {h.descriptor}{art}")
        val = h.value if isinstance(h.value, dict) else {}
        lines.extend(_value_body(val, max_chunk=max_chunk, max_raw=max_raw))
    return "\n".join(lines)


def format_memory_hits_for_perception(
    hits: list[MemoryItem],
) -> tuple[str, list[str | None]]:
    """Perception needs the same value fields plus artifact_index mapping."""
    artifact_by_index: list[str | None] = []
    if not hits:
        return "(no hits)", artifact_by_index

    lines: list[str] = []
    for i, h in enumerate(hits):
        art_note = ""
        if h.artifact_id:
            artifact_by_index.append(h.artifact_id)
            art_note = f" artifact_index={len(artifact_by_index) - 1}"
        else:
            artifact_by_index.append(None)
        lines.append(f"[{i}] kind={h.kind} descriptor={h.descriptor!r}{art_note}")
        val = h.value if isinstance(h.value, dict) else {}
        lines.extend(_value_body(val, max_chunk=500, max_raw=300))

    return "\n".join(lines), artifact_by_index


def summarize_action_result(tool: str, result_text: str) -> str:
    """History line Decision/Perception see on the next iteration."""
    if tool == "search_knowledge":
        body = _expand_search_knowledge_preview(result_text)
        if len(body) > MAX_HISTORY_TOOL_CHARS:
            return body[:MAX_HISTORY_TOOL_CHARS] + "…"
        return body
    if tool == "index_directory":
        try:
            data = json.loads(result_text)
            total = data.get("total_chunks_indexed")
            files = data.get("files_indexed")
            return f"index_directory ok: {files} files, {total} chunks total"
        except json.JSONDecodeError:
            pass
    if tool == "index_document":
        try:
            data = json.loads(result_text)
            n = data.get("chunks_indexed")
            path = data.get("path")
            return f"index_document ok: {path} → {n} chunks"
        except json.JSONDecodeError:
            pass
    if len(result_text) > 400:
        return result_text[:400].replace("\n", " ") + "…"
    return result_text.replace("\n", " ")
