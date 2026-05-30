"""Resolve AI jobs CSV: Kaggle file in data/ai_jobs/raw/ or ~/Downloads/."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "ai_jobs" / "raw"
DEFAULT_RAW = RAW_DIR / "ai_jobs_market_2025_2026.csv"
DOWNLOADS_CSV = Path.home() / "Downloads" / "ai_jobs_market_2025_2026.csv"
KAGGLE_FILENAME = "ai_jobs_market_2025_2026.csv"
# Kaggle release has ~1500 rows; fallback generator writes 80.
MIN_KAGGLE_ROWS = 500


def row_count(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def is_kaggle_dataset(path: Path) -> bool:
    try:
        return row_count(path) >= MIN_KAGGLE_ROWS
    except OSError:
        return False


def resolve_csv(*, copy_from_downloads: bool = True) -> Path:
    """Prefer data/ai_jobs/raw/; optionally copy from ~/Downloads/."""
    if DEFAULT_RAW.is_file() and is_kaggle_dataset(DEFAULT_RAW):
        return DEFAULT_RAW
    if copy_from_downloads and DOWNLOADS_CSV.is_file() and is_kaggle_dataset(DOWNLOADS_CSV):
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DOWNLOADS_CSV, DEFAULT_RAW)
        return DEFAULT_RAW
    if DEFAULT_RAW.is_file():
        return DEFAULT_RAW
    for p in sorted(RAW_DIR.glob("*.csv")):
        return p
    if DOWNLOADS_CSV.is_file():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DOWNLOADS_CSV, DEFAULT_RAW)
        return DEFAULT_RAW
    raise FileNotFoundError(
        f"No AI jobs CSV found. Place {KAGGLE_FILENAME} in {RAW_DIR} "
        f"or at {DOWNLOADS_CSV} (Kaggle download)."
    )
