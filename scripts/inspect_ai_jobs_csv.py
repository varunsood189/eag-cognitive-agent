#!/usr/bin/env python3
"""Print schema stats for the AI jobs CSV (Kaggle dataset)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ai_jobs_data import is_kaggle_dataset, resolve_csv


def main() -> None:
    path = resolve_csv()
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames or []
    print(f"File: {path}")
    print(f"Rows: {len(rows)}")
    print(f"Dataset: {'kaggle (~1500)' if is_kaggle_dataset(path) else 'small/dev'}")
    print(f"Columns ({len(fields)}):")
    for name in fields:
        non_null = sum(1 for r in rows if (r.get(name) or "").strip())
        print(f"  - {name}: {non_null}/{len(rows)} non-empty")
    if rows:
        print("\nSample job_title:", rows[0].get("job_title"))
        print("Sample country:", rows[0].get("country"))


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
