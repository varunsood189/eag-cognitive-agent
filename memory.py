"""Memory service — vector retrieval (FAISS) with keyword fallback."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from gateway import embed as gateway_embed, gateway_chat, parse_structured, response_format_from_model
from schemas import MemoryClassification, MemoryItem, ToolCall
from vector_index import VectorIndex

_BASE_DIR = Path(__file__).resolve().parent


def resolve_state_dir(name: str | None = None) -> Path:
    raw = name if name is not None else os.environ.get("EAG_STATE_DIR", "state")
    p = Path(raw)
    return p if p.is_absolute() else _BASE_DIR / p


STATE_DIR = resolve_state_dir()
MEMORY_PATH = STATE_DIR / "memory.json"
STATE_DIR.mkdir(parents=True, exist_ok=True)
_EMBEDDABLE_KINDS = frozenset({"fact", "preference", "tool_outcome"})

def _is_retrieval_chunk(item: MemoryItem) -> bool:
    val = item.value or {}
    if val.get("chunk"):
        return True
    desc = item.descriptor or ""
    return "[workspace:" in desc or "[corpus:" in desc or "[art:" in desc


def _prioritize_retrieval_hits(hits: list[MemoryItem], top_k: int) -> list[MemoryItem]:
    """Prefer indexed document chunks over query-echo facts in the same vector results."""
    chunks = [h for h in hits if _is_retrieval_chunk(h)]
    if chunks:
        return chunks[:top_k]
    return hits[:top_k]


STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "could should may might shall can to of in for on with at by from as and or "
    "but not no it its this that these those i you he she we they my your his her "
    "their our me him them what which who when where how why if than then so very "
    "just also about into over after before".split()
)


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS and len(t) > 1}


def _try_embed(text: str, task_type: str) -> list[float] | None:
    try:
        resp = gateway_embed(text, task_type=task_type)
        return list(resp["embedding"])
    except Exception as e:
        print(f"[memory] embedding failed ({e!r}); item written without vector")
        return None


class Memory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or MEMORY_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._batch_items: list[MemoryItem] | None = None
        self._batch_index: VectorIndex | None = None

    def begin_batch(self) -> None:
        """Buffer adds in RAM; call commit_batch() once after bulk indexing."""
        self._batch_items = self._reload()
        self._batch_index = VectorIndex(self.path.parent)

    def commit_batch(self) -> None:
        if self._batch_items is None:
            return
        self._save(self._batch_items)
        if self._batch_index is not None and self._batch_index.size > 0:
            self._batch_index.persist()
        self._batch_items = None
        self._batch_index = None

    def _reload(self) -> list[MemoryItem]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        return [MemoryItem.model_validate(x) for x in json.loads(raw)]

    def _save(self, items: list[MemoryItem]) -> None:
        self.path.write_text(
            json.dumps([i.model_dump(mode="json") for i in items], indent=2),
            encoding="utf-8",
        )

    def _index(self) -> VectorIndex:
        idx = VectorIndex(self.path.parent)
        if idx.size == 0:
            for item in self._reload():
                if item.embedding is not None:
                    idx.add(item.id, item.embedding)
            if idx.size > 0:
                idx.persist()
        return idx

    def _persist_item(self, item: MemoryItem) -> MemoryItem:
        if self._batch_items is not None:
            self._batch_items.append(item)
            if (
                item.embedding is not None
                and item.kind in _EMBEDDABLE_KINDS
                and self._batch_index is not None
            ):
                self._batch_index.add(item.id, item.embedding)
            return item
        items = self._reload()
        items.append(item)
        self._save(items)
        if item.embedding is not None and item.kind in _EMBEDDABLE_KINDS:
            idx = self._index()
            idx.add(item.id, item.embedding)
            idx.persist()
        return item

    def _score(self, item: MemoryItem, query_tokens: set[str]) -> float:
        hay = _tokenize(" ".join(item.keywords) + " " + item.descriptor)
        if not query_tokens:
            return 0.0
        overlap = len(query_tokens & hay)
        return overlap / max(len(query_tokens), 1)

    def _keyword_search(
        self,
        query: str,
        history: list[dict],
        *,
        kinds: list[str] | None,
        top_k: int,
    ) -> list[MemoryItem]:
        pool = self._reload()
        if kinds:
            pool = [i for i in pool if i.kind in kinds]
        q_tokens = _tokenize(query)
        for ev in history:
            q_tokens |= _tokenize(
                str(ev.get("text", "")) + " " + str(ev.get("result_descriptor", ""))
            )
        ranked = sorted(pool, key=lambda i: self._score(i, q_tokens), reverse=True)
        return [i for i in ranked if self._score(i, q_tokens) > 0][:top_k] or ranked[:top_k]

    def _vector_search(
        self,
        query: str,
        *,
        kinds: list[str] | None,
        top_k: int,
    ) -> list[MemoryItem]:
        qvec = _try_embed(query, task_type="retrieval_query")
        if qvec is None:
            return []
        idx = self._index()
        if idx.size == 0:
            return []
        hits = idx.search(qvec, k=top_k * 2 if kinds else top_k)
        if not hits:
            return []
        by_id = {item.id: item for item in self._reload()}
        out: list[MemoryItem] = []
        for item_id, _score in hits:
            item = by_id.get(item_id)
            if item is None:
                continue
            if kinds and item.kind not in kinds:
                continue
            out.append(item)
            if len(out) >= top_k:
                break
        return out

    def read(
        self,
        query: str,
        history: list[dict],
        kinds: list[str] | None = None,
        top_k: int = 8,
    ) -> list[MemoryItem]:
        vec_hits = self._vector_search(query, kinds=kinds, top_k=top_k * 2)
        if vec_hits:
            return _prioritize_retrieval_hits(vec_hits, top_k)
        kw = self._keyword_search(query, history, kinds=kinds, top_k=top_k * 2)
        return _prioritize_retrieval_hits(kw, top_k)

    def filter(
        self,
        kinds: list[str] | None = None,
        goal_id: str | None = None,
        recent: int | None = None,
    ) -> list[MemoryItem]:
        pool = self._reload()
        if kinds:
            pool = [i for i in pool if i.kind in kinds]
        if goal_id:
            pool = [i for i in pool if i.goal_id == goal_id]
        pool.sort(key=lambda i: i.created_at, reverse=True)
        if recent:
            pool = pool[:recent]
        return pool

    def remember(
        self,
        raw_text: str,
        source: str,
        run_id: str,
        goal_id: str | None = None,
    ) -> MemoryItem:
        if not raw_text.strip():
            raise ValueError("empty remember text")

        system = (
            "Classify user content into a memory item. "
            "kind must be one of: fact, preference, tool_outcome, scratchpad. "
            "Extract keywords for later search and a short descriptor that includes "
            "any concrete dates, names, and numbers from the content. "
            "Put structured fields in value; if unsure, include {\"raw\": <content>}."
        )
        reply = gateway_chat(
            prompt=f"SOURCE: {source}\nCONTENT:\n{raw_text}",
            system=system,
            auto_route="memory",
            provider="g",
            temperature=0.2,
            max_tokens=1024,
            response_format=response_format_from_model(MemoryClassification),
        )
        classified = parse_structured(reply, MemoryClassification)
        value = classified.value if classified.value else {"raw": raw_text}
        # Question-style queries should not crowd out indexed chunks in vector search.
        if source == "user_query" and classified.kind == "fact":
            lower = raw_text.lower()
            stores_memory = any(
                tok in lower
                for tok in ("birthday", "remember", "reminder", "may", "2026", "note that")
            )
            if not stores_memory:
                classified.kind = "scratchpad"
        embedding = None
        if classified.kind in _EMBEDDABLE_KINDS:
            embedding = _try_embed(classified.descriptor, task_type="retrieval_document")
        item = MemoryItem(
            id=f"mem:{uuid.uuid4().hex[:12]}",
            kind=classified.kind,
            keywords=classified.keywords,
            descriptor=classified.descriptor,
            value=value,
            embedding=embedding,
            source=source,
            run_id=run_id,
            goal_id=goal_id,
            confidence=classified.confidence,
        )
        return self._persist_item(item)

    def record_outcome(
        self,
        tool_call: ToolCall,
        result_text: str,
        artifact_id: str | None,
        run_id: str,
        goal_id: str | None,
    ) -> MemoryItem:
        kw = _tokenize(tool_call.name)
        for v in tool_call.arguments.values():
            kw |= _tokenize(str(v))
        preview_limit = 3_000 if tool_call.name == "search_knowledge" else 800
        desc = f"{tool_call.name}({json.dumps(tool_call.arguments)[:80]}) -> "
        if artifact_id:
            desc += f"artifact {artifact_id}"
        else:
            desc += result_text[:120].replace("\n", " ")
        embedding = _try_embed(desc, task_type="retrieval_document")
        item = MemoryItem(
            id=f"mem:{uuid.uuid4().hex[:12]}",
            kind="tool_outcome",
            keywords=sorted(kw),
            descriptor=desc,
            value={
                "tool": tool_call.name,
                "arguments": tool_call.arguments,
                "result_preview": result_text[:preview_limit],
            },
            artifact_id=artifact_id,
            embedding=embedding,
            source="mcp",
            run_id=run_id,
            goal_id=goal_id,
            confidence=1.0,
        )
        return self._persist_item(item)

    def add_fact(
        self,
        descriptor: str,
        *,
        value: dict | None = None,
        keywords: list[str] | None = None,
        source: str,
        run_id: str,
        goal_id: str | None = None,
    ) -> MemoryItem:
        embedding = _try_embed(descriptor, task_type="retrieval_document")
        item = MemoryItem(
            id=f"mem:{uuid.uuid4().hex[:12]}",
            kind="fact",
            keywords=sorted(keywords or _tokenize(descriptor))[:10],
            descriptor=descriptor,
            value=value or {},
            embedding=embedding,
            source=source,
            run_id=run_id,
            goal_id=goal_id,
            confidence=1.0,
        )
        return self._persist_item(item)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
        VectorIndex(self.path.parent).clear()


memory = Memory(MEMORY_PATH)


def rebind(state_dir: str | None = None) -> Memory:
    """Point module-level memory at a state directory (e.g. state_jobs for Part 2)."""
    global STATE_DIR, MEMORY_PATH, memory
    if state_dir is not None:
        os.environ["EAG_STATE_DIR"] = state_dir
    STATE_DIR = resolve_state_dir()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH = STATE_DIR / "memory.json"
    memory = Memory(MEMORY_PATH)
    return memory


# Module-level aliases (S7 MCP server calls these directly).
def read(
    query: str,
    history: list[dict] | None = None,
    *,
    kinds: list[str] | None = None,
    top_k: int = 8,
) -> list[MemoryItem]:
    return memory.read(query, history or [], kinds=kinds, top_k=top_k)


def add_fact(
    descriptor: str,
    *,
    value: dict | None = None,
    keywords: list[str] | None = None,
    source: str,
    run_id: str,
    goal_id: str | None = None,
) -> MemoryItem:
    return memory.add_fact(
        descriptor,
        value=value,
        keywords=keywords,
        source=source,
        run_id=run_id,
        goal_id=goal_id,
    )


def clear() -> None:
    memory.clear()
