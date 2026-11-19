# EAG Cognitive Agent

A four-role LLM agent (**Memory → Perception → Decision → Action**) with **FAISS-backed RAG**, **stdio MCP tools**, and a gated planner that never sees tool names.  
Built for multi-step research, document indexing, and semantic Q&A over a local knowledge base.  
Stack: Python 3.11+, Pydantic contracts, FastMCP, FAISS, and an LLM gateway (chat + embed).

> **What a recruiter should notice:** role separation with an architectural gate (Perception plans intent only; Decision alone picks MCP tools), persistent vector memory across runs, and **26 pytest** cases that run without a live gateway.

---

## Architecture

```
User query
  → memory.remember(query)
  → loop (max 24 iterations):
       memory.read(query, history)          # FAISS vector search → keyword fallback
       perception.observe → goals + done flags
       if all done → break
       decision.next_step(ONE goal) → final answer OR one MCP tool
       action.execute → memory.record_outcome (+ artifact if payload >4KB)
  → final answer from run history
```

| Role | Responsibility |
|------|----------------|
| **Memory** | FAISS embeddings + keyword fallback; persists in `state/memory.json` + `state/index.faiss` |
| **Perception** | Plans goals and marks progress (intent only — no tool names in its system prompt) |
| **Decision** | Sees **one** goal; answers or calls a single MCP tool |
| **Action** | Executes MCP tools; large results → content-addressable `art:…` store |

**Architectural gate:** tool names live in MCP docstrings + `prompts/decision_system.txt`, never in Perception’s system prompt. Enforce with:

```bash
./scripts/check-perception-gate.sh
uv run pytest tests/test_perception_gate.py -q
```

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐     ┌──────────┐
│   Memory    │────▶│  Perception  │────▶│  Decision  │────▶│  Action  │
│ FAISS + RAG │     │ goals / done │     │ 1 tool/ans │     │ MCP stdio│
└─────────────┘     └──────────────┘     └────────────┘     └──────────┘
       ▲                                                       │
       └──────────────── record_outcome / artifacts ───────────┘
```

---

## MCP tools (12)

| Tool | Purpose |
|------|---------|
| `web_search` | DuckDuckGo (optional Tavily fallback) |
| `fetch_url` | HTTP fetch; Wikipedia API when possible |
| `get_time` | Time in a named timezone |
| `currency_convert` | FX conversion |
| `read_file` / `list_dir` / `create_file` / `update_file` / `edit_file` | Sandboxed under `workspace/` |
| `index_document` | Chunk + embed one workspace file or artifact into Memory |
| `index_directory` | Index all `*.md` under a workspace folder |
| `search_knowledge` | Vector search over indexed fact chunks |

---

## Quick start

### Prerequisites

1. **Python 3.11+** and [uv](https://docs.astral.sh/uv/)
2. **LLM Gateway V7** on port **8107** (chat + `/v1/embed`)
3. **Ollama** with `nomic-embed-text` (`ollama pull nomic-embed-text`)
4. API keys in `.env` (copy from `.env.example`)

`gateway.py` auto-detects V7 then V2 under common paths (`./llm_gatewayV7`, parent folder, etc.).

### Install and run

```bash
git clone https://github.com/varunsood189/eag-cognitive-agent.git
cd eag-cognitive-agent
cp .env.example .env   # add GEMINI_API_KEY (optional TAVILY_API_KEY)
uv sync

# Terminal A — gateway
cd path/to/llm_gatewayV7 && ./run.sh   # http://localhost:8107

# Terminal B — agent
rm -rf state workspace && mkdir -p state workspace workspace/papers
cp papers/*.md workspace/papers/
./scripts/run.sh python agent7.py --preset a
# or: ./scripts/run.sh python agent7.py --query "Your question here"
```

`./scripts/run.sh` clears a stale `VIRTUAL_ENV` so `uv` uses this project’s venv.

Presets: **a–d** (baseline tool use), **e** (index one paper), **f1**/**f2** (index corpus then cross-run query — keep `state/` between them), **g** (semantic recall), **h** (cross-paper compare), **j1–j5** (AI jobs RAG on `state_jobs/`).

All target queries:

```bash
./scripts/run_all_queries.sh   # logs → logs/
```

---

## Proof

Gateway-free unit tests cover schemas, memory keyword/vector paths, perception history + architectural gate, prompt rendering, artifacts, and the AI jobs corpus manifest:

```bash
uv sync --extra dev
uv run pytest -q
```

| Check | Command |
|-------|---------|
| Full suite | `uv run pytest` (**26** tests in `tests/`) |
| Perception/Decision gate | `./scripts/check-perception-gate.sh` |
| No secrets in tree | `./scripts/check-no-secrets.sh` |

Architecture write-ups: [project guide PDF](docs/EAG_Cognitive_Agent_Architecture.pdf) · [IEEE-style PDF](docs/EAG_Cognitive_Agent_Architecture_IEEE.pdf) · [rendering checklist](docs/rendering-inquiry-checklist.md)

---

## AI Jobs Market RAG

Corpus: [Kaggle — AI Jobs Market 2025-2026 Salaries](https://www.kaggle.com/datasets/alitaqishah/ai-jobs-market-2025-2026-salaries) — **1500** markdown items under `corpus/ai_jobs/items/` (`corpus/ai_jobs/manifest.json`).

```bash
./scripts/import_kaggle_csv.sh ~/Downloads/ai_jobs_market_2025_2026.csv
uv run python scripts/build_ai_jobs_corpus.py
uv run python scripts/index_ai_jobs_corpus.py   # → state_jobs/

./scripts/run.sh python jobs_rag.py --preset q1
./scripts/run_custom_rag_traces.sh              # docs/traces/custom-q*-*.txt
```

Offline without Kaggle: `uv run python scripts/generate_fallback_ai_jobs_csv.py` (80 rows).

| ID | Query type |
|----|------------|
| q1–q3 | semantic |
| q4 | factual |
| q5 | comparison |

---

## Project layout

| Area | Path |
|------|------|
| Orchestrator | `agent7.py` |
| Roles | `memory.py`, `perception.py`, `decision.py`, `action.py` |
| Contracts | `schemas.py` |
| Vector index | `vector_index.py` → `state/index.faiss` |
| MCP server | `mcp_server.py` (stdio, 12 tools) |
| LLM client | `gateway.py` |
| Prompts / tests / docs | `prompts/`, `tests/`, `docs/` |
| Jobs RAG | `jobs_rag.py`, `corpus/ai_jobs/` |

Runtime dirs (`state/`, `state_jobs/`, `workspace/`, `logs/`), `.env`, and Kaggle CSV under `data/ai_jobs/raw/` are gitignored — rebuild locally after clone.

### Environment

| Variable | Default | Notes |
|----------|---------|--------|
| `LLM_GATEWAY_V7_URL` | `http://localhost:8107` | Preferred gateway |
| `LLM_GATEWAY_V2_URL` | `http://localhost:8100` | Fallback |
| `TAVILY_API_KEY` | — | Optional; improves `web_search` |
| `GEMINI_API_KEY` | — | Required for gateway |
| `EAG_STATE_DIR` | `state` | Use `state_jobs` for presets **j1–j5** |

---

## License

[MIT](LICENSE)
