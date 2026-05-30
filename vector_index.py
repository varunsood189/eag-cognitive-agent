"""FAISS-backed vector index for Session 7 Memory."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

_faiss_mod = None


def _get_faiss():
    global _faiss_mod
    if _faiss_mod is None:
        try:
            import faiss as f  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "faiss-cpu is required for Session 7. Run: uv sync"
            ) from e
        _faiss_mod = f
    return _faiss_mod


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        return vec
    return vec / norm


class VectorIndex:
    """In-memory FAISS IndexFlatIP with disk persistence under state/."""

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_dir / "index.faiss"
        self.ids_path = self.store_dir / "index_ids.json"
        self._index = None
        self._ids: list[str] = []
        self._dim: int | None = None
        self._load()

    def _load(self) -> None:
        if self.index_path.exists() and self.ids_path.exists():
            self._index = _get_faiss().read_index(str(self.index_path))
            self._ids = json.loads(self.ids_path.read_text(encoding="utf-8"))
            self._dim = self._index.d

    def persist(self) -> None:
        if self._index is None:
            return
        _get_faiss().write_index(self._index, str(self.index_path))
        self.ids_path.write_text(json.dumps(self._ids), encoding="utf-8")

    def clear(self) -> None:
        self._index = None
        self._ids = []
        self._dim = None
        if self.index_path.exists():
            self.index_path.unlink()
        if self.ids_path.exists():
            self.ids_path.unlink()

    def add(self, item_id: str, embedding: list[float]) -> None:
        vec = _l2_normalize(np.array(embedding, dtype=np.float32))
        if self._index is None:
            self._dim = vec.shape[0]
            self._index = _get_faiss().IndexFlatIP(self._dim)
        elif vec.shape[0] != self._dim:
            raise ValueError(
                f"Embedding dim {vec.shape[0]} does not match index dim {self._dim}. "
                "Keep the gateway embedding model fixed for the lifetime of an index."
            )
        self._index.add(vec.reshape(1, -1))
        self._ids.append(item_id)

    def search(self, query_embedding: list[float], k: int = 5) -> list[tuple[str, float]]:
        if self._index is None or self._index.ntotal == 0:
            return []
        vec = _l2_normalize(np.array(query_embedding, dtype=np.float32))
        scores, idxs = self._index.search(vec.reshape(1, -1), min(k, self._index.ntotal))
        out: list[tuple[str, float]] = []
        for score, idx in zip(scores[0].tolist(), idxs[0].tolist()):
            if idx < 0:
                continue
            out.append((self._ids[idx], float(score)))
        return out

    @property
    def size(self) -> int:
        return self._index.ntotal if self._index is not None else 0
