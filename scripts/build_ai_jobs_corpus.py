#!/usr/bin/env python3
"""Convert AI jobs CSV into corpus/ai_jobs/items/*.md and update manifest.json."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ai_jobs_data import KAGGLE_FILENAME, is_kaggle_dataset, resolve_csv

ITEMS_DIR = ROOT / "corpus" / "ai_jobs" / "items"
MANIFEST_PATH = ROOT / "corpus" / "ai_jobs" / "manifest.json"

KAGGLE_URL = "https://www.kaggle.com/datasets/alitaqishah/ai-jobs-market-2025-2026-salaries"


def _bool_remote(row: dict) -> str:
    if str(row.get("is_remote_friendly", "0")).strip() in ("1", "True", "true"):
        return "yes"
    rw = (row.get("remote_work") or "").lower()
    if "remote" in rw:
        return "yes"
    return "no"


def row_to_markdown(row: dict, seq: int) -> str:
    job_id = (row.get("job_id") or f"job-{seq:04d}").strip()
    title = row.get("job_title") or "Unknown role"
    category = row.get("job_category") or ""
    exp = row.get("experience_level") or ""
    yoe = row.get("years_of_experience") or ""
    edu = row.get("education_required") or ""
    annual = row.get("annual_salary_usd") or ""
    smin = row.get("salary_min_usd") or ""
    smax = row.get("salary_max_usd") or ""
    city = row.get("city") or ""
    country = row.get("country") or ""
    remote = _bool_remote(row)
    size = row.get("company_size") or ""
    industry = row.get("industry") or ""
    skills = row.get("required_skills") or ""
    tier = row.get("salary_tier") or ""
    llm = row.get("is_llm_role") or "0"
    premium = row.get("ai_salary_premium_pct") or ""

    prose = (
        f"This posting is for a {title} role in the {category} track. "
        f"The position is classified as {exp} level with roughly {yoe} years of experience expected "
        f"and {edu} education. Compensation is about {annual} USD annually "
        f"(range {smin}–{smax} USD). The role is based in {city}, {country}, "
        f"with remote-friendly status: {remote}. Company size is {size} in the {industry} sector. "
        f"Key skills include {skills}. Salary tier: {tier}. "
        f"LLM-focused role flag: {llm}. AI salary premium percent: {premium}."
    )

    return f"""---
job_id: {job_id}
corpus_id: ai_jobs/{job_id}
job_title: {title}
job_category: {category}
experience_level: {exp}
country: {country}
city: {city}
remote_friendly: {remote}
annual_salary_usd: {annual}
is_llm_role: {llm}
---

# {title}

- **Category:** {category}
- **Experience:** {exp} ({yoe} years)
- **Education:** {edu}
- **Salary (USD):** {annual} (min {smin}, max {smax})
- **Location:** {city}, {country}
- **Remote-friendly:** {remote}
- **Company size:** {size}
- **Industry:** {industry}
- **Skills:** {skills}
- **Salary tier:** {tier}

## Summary

{prose}
"""


def main() -> None:
    csv_path = resolve_csv()
    with csv_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if len(rows) < 50:
        raise SystemExit(f"Need at least 50 rows; found {len(rows)} in {csv_path}")
    if not is_kaggle_dataset(csv_path):
        raise SystemExit(
            f"{csv_path} has only {len(rows)} rows. For the assignment use the Kaggle CSV "
            f"(~1500 rows): ./scripts/import_kaggle_csv.sh ~/Downloads/{KAGGLE_FILENAME}"
        )

    ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    for old in ITEMS_DIR.glob("*.md"):
        old.unlink()

    written: list[str] = []
    for i, row in enumerate(rows, start=1):
        job_id = (row.get("job_id") or f"job-{i:04d}").strip()
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in job_id)[:64]
        fname = f"{i:04d}_{safe}.md"
        path = ITEMS_DIR / fname
        path.write_text(row_to_markdown(row, i), encoding="utf-8")
        written.append(fname)

    manifest = {
        "name": "AI Jobs Market 2025-2026 Salaries",
        "source_url": KAGGLE_URL,
        "source_file": KAGGLE_FILENAME,
        "local_csv": str(csv_path.relative_to(ROOT)),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(written),
        "item_format": "markdown",
        "items_dir": "corpus/ai_jobs/items",
        "columns": list(rows[0].keys()) if rows else [],
        "license_note": "Kaggle CSV in data/ai_jobs/raw/ (import via scripts/import_kaggle_csv.sh).",
        "row_count": len(rows),
        "dataset": "kaggle" if is_kaggle_dataset(csv_path) else "small",
        "build_command": "python scripts/build_ai_jobs_corpus.py",
        "index_command": "python scripts/index_ai_jobs_corpus.py",
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(written)} items under {ITEMS_DIR}")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
