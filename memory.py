"""Memory service — keyword read, LLM classify on remember, deterministic outcomes."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from gateway import gateway_chat, parse_structured, response_format_from_model
from schemas import MemoryClassification, MemoryItem, ToolCall

STATE_DIR = Path(__file__).resolve().parent / "state"
MEMORY_PATH = STATE_DIR / "memory.json"

STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "could should may might shall can to of in for on with at by from as and or "
    "but not no it its this that these those i you he she we they my your his her "
    "their our me him them what which who when where how why if than then so very "
    "just also about into over after before".split()
)


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS and len(t) > 1}


class Memory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or MEMORY_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[MemoryItem] = []
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        if self.path.exists():
            raw = self.path.read_text(encoding="utf-8").strip()
            if raw:
                import json

                data = json.loads(raw)
                self._items = [MemoryItem.model_validate(x) for x in data]
        self._loaded = True

    def _save(self) -> None:
        import json

        self.path.write_text(
            json.dumps([i.model_dump(mode="json") for i in self._items], indent=2),
            encoding="utf-8",
        )

    def _score(self, item: MemoryItem, query_tokens: set[str]) -> float:
        hay = _tokenize(" ".join(item.keywords) + " " + item.descriptor)
        if not query_tokens:
            return 0.0
        overlap = len(query_tokens & hay)
        return overlap / max(len(query_tokens), 1)

    def read(
        self,
        query: str,
        history: list[dict],
        kinds: list[str] | None = None,
        top_k: int = 8,
    ) -> list[MemoryItem]:
        self._load()
        q_tokens = _tokenize(query)
        for ev in history:
            q_tokens |= _tokenize(str(ev.get("text", "")) + " " + str(ev.get("result_descriptor", "")))
        pool = self._items
        if kinds:
            pool = [i for i in pool if i.kind in kinds]
        ranked = sorted(pool, key=lambda i: self._score(i, q_tokens), reverse=True)
        return [i for i in ranked if self._score(i, q_tokens) > 0][:top_k] or ranked[:top_k]

    def filter(
        self,
        kinds: list[str] | None = None,
        goal_id: str | None = None,
        recent: int | None = None,
    ) -> list[MemoryItem]:
        self._load()
        pool = list(self._items)
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
        self._load()
        if not raw_text.strip():
            raise ValueError("empty remember text")

        system = (
            "Classify user content into a memory item. "
            "kind must be one of: fact, preference, tool_outcome, scratchpad. "
            "Extract keywords for later search and a short descriptor."
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
        item = MemoryItem(
            id=f"mem:{uuid.uuid4().hex[:12]}",
            kind=classified.kind,
            keywords=classified.keywords,
            descriptor=classified.descriptor,
            value=classified.value,
            source=source,
            run_id=run_id,
            goal_id=goal_id,
            confidence=classified.confidence,
        )
        self._items.append(item)
        self._save()
        return item

    def record_outcome(
        self,
        tool_call: ToolCall,
        result_text: str,
        artifact_id: str | None,
        run_id: str,
        goal_id: str | None,
    ) -> MemoryItem:
        self._load()
        kw = _tokenize(tool_call.name)
        for v in tool_call.arguments.values():
            kw |= _tokenize(str(v))
        desc = result_text[:200].replace("\n", " ")
        item = MemoryItem(
            id=f"mem:{uuid.uuid4().hex[:12]}",
            kind="tool_outcome",
            keywords=sorted(kw),
            descriptor=desc,
            value={
                "tool": tool_call.name,
                "arguments": tool_call.arguments,
                "result_preview": result_text[:500],
            },
            artifact_id=artifact_id,
            source="mcp",
            run_id=run_id,
            goal_id=goal_id,
            confidence=1.0,
        )
        self._items.append(item)
        self._save()
        return item


memory = Memory()
