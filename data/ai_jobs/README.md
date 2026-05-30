# AI Jobs raw data

Place the Kaggle CSV here:

- **Dataset:** [AI Jobs Market 2025-2026 Salaries](https://www.kaggle.com/datasets/alitaqishah/ai-jobs-market-2025-2026-salaries)
- **Expected filename:** `raw/ai_jobs_market_2025_2026.csv` (~1500 rows)

```bash
# Recommended — uses your Kaggle download (1500 rows):
./scripts/import_kaggle_csv.sh ~/Downloads/ai_jobs_market_2025_2026.csv

# Or copy manually:
cp ~/Downloads/ai_jobs_market_2025_2026.csv data/ai_jobs/raw/

# build_ai_jobs_corpus.py also copies from ~/Downloads/ if raw/ is empty or only has a small dev CSV.

# Optional: Kaggle CLI
kaggle datasets download -d alitaqishah/ai-jobs-market-2025-2026-salaries -p data/ai_jobs/raw --unzip

# Local dev only (80 rows) if you have no Kaggle file at all:
uv run python scripts/generate_fallback_ai_jobs_csv.py
```

Then:

```bash
uv run python scripts/inspect_ai_jobs_csv.py
uv run python scripts/build_ai_jobs_corpus.py
uv run python scripts/index_ai_jobs_corpus.py
# Shows a tqdm progress bar; expect ~10–20 minutes for 1500 items.
```
