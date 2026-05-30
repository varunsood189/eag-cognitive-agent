# EAG Cognitive Agent

**EAG V3 Session 7** — four-role agentic architecture with **FAISS vector memory** (RAG): **Memory**, **Perception**, **Decision**, and **Action**, orchestrated in `agent7.py` with eleven MCP tools and **LLM Gateway V7** (`/v1/embed` + chat).

> **Security:** Put API keys only in `.env` (gitignored). Commit **`.env.example`** (placeholders only). Before pushing, run `./scripts/check-no-secrets.sh`.

## What this repo contains

| Area | Files |
|------|--------|
| Orchestrator | `agent7.py` |
| Roles | `memory.py`, `perception.py`, `decision.py`, `action.py` |
| Contracts | `schemas.py` |
| Vector index | `vector_index.py` → `state/index.faiss`, `index_ids.json` |
| Tools | `mcp_server.py` (stdio MCP, 12 tools) |
| LLM client | `gateway.py` |
| Artifacts | `artifacts.py` → `state/artifacts/` (runtime, gitignored) |
| Prompts | `prompts/` |
| Tests | `tests/` (no gateway required) |
| Docs | `docs/` — architecture PDF, HTML guides, Part 2 traces |
| Scripts | `scripts/run_all_queries.sh`, `scripts/run_queries.sh` |

**Not in git:** runtime dirs (`state/`, `state_jobs/`, `workspace/`, `logs/`), secrets (`.env`), Kaggle CSV (`data/ai_jobs/raw/`), `.venv/`, and local gateway installs. See [Git & GitHub](#git--github).

## Architecture

```
User query
  → memory.remember(query)
  → loop (max 24 iterations):
       memory.read(query, history)
       perception.observe → goal list + done flags
       if all done → break
       decision.next_step(ONE goal) → answer OR one MCP tool
       action.execute → memory.record_outcome (+ artifact if large)
  → final answer from run history
```

- **Perception** — plans goals, marks progress, attaches artifact IDs when needed (Gemini `provider=g`).
- **Decision** — sees **one** goal only; answers or calls a single tool.
- **Action** — runs MCP tools; payloads >4KB → content-addressable `art:…` store.
- **Memory** — vector search first (FAISS over embeddings), keyword fallback; `state/memory.json` + index files persist across runs (`c2`, `f2` need prior run state).

## MCP tools

| Tool | Purpose |
|------|---------|
| `web_search` | DuckDuckGo (optional Tavily fallback) |
| `fetch_url` | HTTP fetch; Wikipedia uses API when possible |
| `get_time` | Time in a named timezone |
| `currency_convert` | FX conversion |
| `read_file` | Read under `workspace/` |
| `list_dir` | List under `workspace/` |
| `create_file` | Create under `workspace/` |
| `update_file` | Overwrite under `workspace/` |
| `edit_file` | Search/replace under `workspace/` |
| `index_document` | Chunk + embed one workspace file or artifact into Memory |
| `index_directory` | Index all `*.md` files under a workspace folder (preset f1) |
| `search_knowledge` | Vector search over indexed fact chunks |

Course papers for presets **e–h** are in `papers/` (copied into `workspace/papers/` when you run the agent or `scripts/run_all_queries.sh`).

## Prerequisites

1. **Python 3.11+** and [uv](https://docs.astral.sh/uv/)
2. **LLM Gateway V7** (port **8107**; chat + embed)
3. **Ollama** with `nomic-embed-text` for embeddings (`ollama pull nomic-embed-text`)
4. **API keys** in `.env` (see [Environment variables](#environment-variables))

Place `llm_gatewayV7` next to this project or on `PYTHONPATH`. `gateway.py` auto-detects V7 then V2 and searches common paths (`./llm_gatewayV7`, parent folder, etc.).

## Quick start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd eag-cognitive-agent
cp .env.example .env
# Edit .env — add GEMINI_API_KEY (and optional TAVILY_API_KEY)

uv sync
```

If you see `VIRTUAL_ENV=.../Assignment 6/... does not match the project environment`, your shell still points at the old checkout. Fix once per terminal:

```bash
deactivate 2>/dev/null || true
unset VIRTUAL_ENV
cd "/path/to/Assignment 7/eag-cognitive-agent"
uv sync
```

Or use the project wrapper (clears stale `VIRTUAL_ENV` automatically):

```bash
./scripts/run.sh python agent7.py --preset a
```

### 2. Start the LLM Gateway (separate terminal)

```bash
cd path/to/llm_gatewayV7
./run.sh
# Listens on http://localhost:8107
```

### 3. Run the agent

Clean runtime state before most presets (skip between `c1` and `c2` so memory persists):

```bash
rm -rf state workspace && mkdir -p state workspace workspace/papers
cp papers/*.md workspace/papers/
```

Single preset:

```bash
./scripts/run.sh python agent7.py --preset a
# or, after unset VIRTUAL_ENV:  uv run python agent7.py --preset a
./scripts/run.sh python agent7.py --query "Your question here"
```

All course target queries (logged to `logs/`):

```bash
./scripts/run_all_queries.sh
```

Presets: **a–d** (Session 6 regression), **e** (index one paper), **f1** / **f2** (index corpus then cross-run query — keep `state/` between f1 and f2), **g** (semantic recall), **h** (cross-paper compare), **j1–j5** (Part 2 AI jobs RAG — uses `state_jobs/`, index corpus first).

## Part 2 — AI Jobs Market RAG

**Corpus:** [Kaggle — AI Jobs Market 2025-2026 Salaries](https://www.kaggle.com/datasets/alitaqishah/ai-jobs-market-2025-2026-salaries) (**1500** markdown items under `corpus/ai_jobs/items/`; see `corpus/ai_jobs/manifest.json`). Import: `./scripts/import_kaggle_csv.sh ~/Downloads/ai_jobs_market_2025_2026.csv`

### Build and index

```bash
# Real Kaggle CSV (default path after manual download):
./scripts/import_kaggle_csv.sh ~/Downloads/ai_jobs_market_2025_2026.csv

# Or build steps only (auto-copies from ~/Downloads/ if raw/ is missing):
uv run python scripts/build_ai_jobs_corpus.py
uv run python scripts/index_ai_jobs_corpus.py   # → state_jobs/ (~1500 embeds; several minutes)

# Offline dev only (80 rows) when you have no Kaggle file:
uv run python scripts/generate_fallback_ai_jobs_csv.py
```

### Custom queries (CLI)

| ID | Query | Type |
|----|--------|------|
| q1 | Which roles offer strong pay for people who never manage staff and focus on hands-on modeling work? | semantic |
| q2 | Where can someone work fully from home in machine learning and still earn above two hundred thousand dollars? | semantic |
| q3 | What jobs suit someone at the very beginning of their career outside the United States? | semantic |
| q4 | What is the highest listed compensation for a position centered on natural language processing or large language models? | factual |
| q5 | How does typical pay for AI engineers compare to data scientists when both are based in the United Kingdom? | comparison |

```bash
./scripts/run.sh python jobs_rag.py --preset q1
./scripts/run.sh python jobs_rag.py --preset q1 --no-index
./scripts/run_custom_rag_traces.sh    # docs/traces/custom-q*-*.txt
./scripts/run_custom_queries.sh       # agent7 j1–j5 on state_jobs/
```

**Architectural gate (Session 7):** Perception plans in **intent only**; Decision picks MCP tools (tool names live in MCP **docstrings** + `prompts/decision_system.txt`, never in Perception’s system prompt).

```bash
./scripts/check-perception-gate.sh   # scans all tools in mcp_server.py
uv run pytest tests/test_perception_gate.py -q
```

To add a tool for a new corpus format: implement it in `mcp_server.py` with a clear docstring, extend `prompts/decision_system.txt`, re-run the gate above.

When a role misbehaves, use [docs/rendering-inquiry-checklist.md](docs/rendering-inquiry-checklist.md) — fix `prompt_render.py` / history summarisation before adding SYSTEM rules.

**Architecture PDFs:**

| Document | Format |
|----------|--------|
| [docs/EAG_Cognitive_Agent_Architecture.pdf](docs/EAG_Cognitive_Agent_Architecture.pdf) | Project guide (single-column) |
| [docs/EAG_Cognitive_Agent_Architecture_IEEE.pdf](docs/EAG_Cognitive_Agent_Architecture_IEEE.pdf) | IEEE conference style (two-column, Abstract, Index Terms, numbered sections) |

Regenerate both:

```bash
./scripts/build_architecture_pdf.sh          # also builds IEEE PDF
./scripts/build_architecture_pdf_ieee.sh     # IEEE only
```

### 4. Tests

```bash
uv run pytest
```

## Environment variables

| Variable | Default | Notes |
|----------|---------|--------|
| `LLM_GATEWAY_V7_URL` | `http://localhost:8107` | Preferred gateway |
| `LLM_GATEWAY_V2_URL` | `http://localhost:8100` | Fallback |
| `TAVILY_API_KEY` | — | Optional; improves `web_search` when DDG is rate-limited |
| `GEMINI_API_KEY` | — | Required for gateway (set in `.env` or gateway folder) |
| `EAG_STATE_DIR` | `state` | Use `state_jobs` for Part 2 presets **j1–j5** and isolated FAISS index |

Provider keys are read by the gateway from this project's `.env` and/or the gateway's own `.env`.

## Project layout

```
eag-cognitive-agent/
├── agent7.py              # Main loop + CLI
├── memory.py
├── perception.py
├── decision.py
├── action.py
├── schemas.py
├── gateway.py
├── artifacts.py
├── mcp_server.py
├── prompts/
├── tests/
├── scripts/
├── docs/
├── jobs_rag.py            # Part 2 CLI
├── jobs_rag_queries.py    # q1–q5 + j1–j5 text
├── indexing.py            # shared chunk → Memory
├── corpus/ai_jobs/        # Part 2 corpus + manifest
├── state/                 # gitignored — course memory
├── state_jobs/            # gitignored — Part 2 FAISS index
├── workspace/             # gitignored — agent file I/O
└── logs/                  # gitignored — run logs from scripts
```

## Git & GitHub

### What to commit

| Track | Purpose |
|-------|---------|
| Source (`*.py`), `prompts/`, `tests/`, `scripts/` | Agent + Part 2 pipeline |
| `papers/`, `corpus/ai_jobs/` (manifest + `items/*.md`) | Course papers + rebuilt job corpus (~1500 items) |
| `docs/` (guides, `docs/traces/custom-*.txt`) | Assignment traces |
| `data/ai_jobs/README.md` | How to obtain the Kaggle CSV |
| `pyproject.toml`, `uv.lock`, `.env.example` | Reproducible install; no secrets |
| `.vscode/settings.json` | Optional: correct `uv` / venv for this repo |

### Never commit (`.gitignore`)

| Ignore | Why |
|--------|-----|
| `.env`, `.env.*` (except `.env.example`) | API keys |
| `state/`, `state_jobs/` | FAISS + `memory.json` (~tens of MB; rebuild locally) |
| `workspace/`, `logs/` | Runtime files and run logs |
| `data/ai_jobs/raw/*.csv` | Kaggle license / size — download after clone |
| `.venv/`, `llm_gatewayV7/` | Machine-local installs |
| `readme_output_prompts.md` | Local prompt dumps |

After clone, each developer runs: `cp .env.example .env`, import CSV, `index_ai_jobs_corpus.py` (see [Part 2](#part-2--ai-jobs-market-rag)).

### First push / update checklist

```bash
cp .env.example .env          # add keys locally only — never commit .env
./scripts/check-no-secrets.sh
git status                    # .env, state/, state_jobs/, logs/ must not appear
git add -A
git status                    # review: no raw CSV, no memory.json
git commit -m "Session 7 agent + Part 2 AI jobs RAG"
git push
```

If `.env` or `state_jobs/` was ever pushed, rotate keys and remove those paths from history before sharing the repo.

### Clone on a new machine

```bash
git clone <your-repo-url>
cd eag-cognitive-agent
cp .env.example .env
# Edit .env — GEMINI_API_KEY, optional TAVILY_API_KEY
uv sync
# Gateway + Ollama (see Prerequisites), then Part 2:
./scripts/import_kaggle_csv.sh ~/Downloads/ai_jobs_market_2025_2026.csv
uv run python scripts/index_ai_jobs_corpus.py
```

readme for a-h
/eag-cognitive-agent/readme_output_prompts.md
for part 2 
/eag-cognitive-agent/logs/custom-agent7-20260529-213113.log

## License

See [LICENSE](LICENSE).
