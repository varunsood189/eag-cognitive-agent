"""Part 2 corpus smoke tests (no gateway)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "corpus" / "ai_jobs" / "items"
MANIFEST = ROOT / "corpus" / "ai_jobs" / "manifest.json"


def test_manifest_exists_after_build() -> None:
    if not MANIFEST.is_file() or len(list(ITEMS.glob("*.md"))) < 50:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_ai_jobs_corpus.py")],
            check=True,
            cwd=ROOT,
        )
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["item_count"] >= 50
    assert (ITEMS).is_dir()
    md_files = list(ITEMS.glob("*.md"))
    assert len(md_files) >= 50


def test_corpus_items_contain_salary_prose() -> None:
    if not ITEMS.is_dir():
        return
    sample = next(ITEMS.glob("*.md"))
    text = sample.read_text(encoding="utf-8")
    assert "annual_salary_usd" in text or "Salary" in text
