"""Content-addressable artifact store for large tool payloads."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from schemas import Artifact

ARTIFACT_THRESHOLD_BYTES = 4096
STATE_DIR = Path(__file__).resolve().parent / "state"
ARTIFACTS_DIR = STATE_DIR / "artifacts"


class ArtifactStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ARTIFACTS_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        blob: bytes,
        *,
        content_type: str = "text/plain",
        source: str,
        descriptor: str,
    ) -> str:
        digest = hashlib.sha256(blob).hexdigest()[:16]
        artifact_id = f"art:{digest}"
        bin_path = self.root / f"{artifact_id}.bin"
        meta_path = self.root / f"{artifact_id}.json"
        if not bin_path.exists():
            bin_path.write_bytes(blob)
            meta = Artifact(
                id=artifact_id,
                content_type=content_type,
                size_bytes=len(blob),
                source=source,
                descriptor=descriptor[:500],
            )
            meta_path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        return artifact_id

    def get_bytes(self, artifact_id: str) -> bytes:
        path = self.root / f"{artifact_id}.bin"
        if not path.exists():
            raise FileNotFoundError(artifact_id)
        return path.read_bytes()

    def get_meta(self, artifact_id: str) -> Artifact:
        path = self.root / f"{artifact_id}.json"
        if not path.exists():
            raise FileNotFoundError(artifact_id)
        return Artifact.model_validate_json(path.read_text(encoding="utf-8"))

    def exists(self, artifact_id: str) -> bool:
        return (self.root / f"{artifact_id}.bin").exists()

    def list_ids(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("art:*.json"))
