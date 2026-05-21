"""Artifact store tests."""

from pathlib import Path

from artifacts import ARTIFACT_THRESHOLD_BYTES, ArtifactStore


def test_put_get_exists(tmp_path: Path) -> None:
    store = ArtifactStore(root=tmp_path)
    blob = b"x" * (ARTIFACT_THRESHOLD_BYTES + 100)
    art_id = store.put(blob, source="test", descriptor="big")
    assert store.exists(art_id)
    assert store.get_bytes(art_id) == blob
    meta = store.get_meta(art_id)
    assert meta.size_bytes == len(blob)
