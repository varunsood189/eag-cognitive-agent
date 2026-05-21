# EAG Cognitive Agent

**EAG V3 Session 6** — four-role agentic architecture: **Memory**, **Perception**, **Decision**, and **Action**, orchestrated in `agent6.py` with Pydantic contracts, nine MCP tools, and the course **LLM Gateway** as the only LLM backend.

> **Security:** Put API keys only in `.env` (gitignored). Commit **`.env.example`** (placeholders only). Before pushing, run `./scripts/check-no-secrets.sh`.

## What this repo contains

| Area | Files |
|------|--------|
| Orchestrator | `agent6.py` |
| Roles | `memory.py`, `perception.py`, `decision.py`, `action.py` |
| Contracts | `schemas.py` |
| Tools | `mcp_server.py` (stdio MCP) |
| LLM client | `gateway.py` |
| Artifacts | `artifacts.py` → `state/artifacts/` (runtime, gitignored) |
| Prompts | `prompts/` |
| Tests | `tests/` (no gateway required) |
| Docs | `docs/` — HTML guides and `Assignment6_Project_Overview.md` |
| Scripts | `scripts/run_all_queries.sh`, `scripts/run_queries.sh` |

**Not in git:** `state/`, `workspace/`, `logs/`, `.env`, `.venv/`, and optionally `llm_gatewayV3/` (install beside this project; see [Prerequisites](#prerequisites)).

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
- **Memory** — `state/memory.json` persists across runs (preset `c2` depends on this).

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

## Prerequisites

1. **Python 3.11+** and [uv](https://docs.astral.sh/uv/)
2. **LLM Gateway V3** from course materials (port **8101**, or V2 on **8100**)
3. **API keys** in `.env` (see [Environment variables](#environment-variables))

Place `llm_gatewayV3` next to this project or on `PYTHONPATH`. `gateway.py` auto-detects V3 then V2 and searches common paths (`./llm_gatewayV3`, parent folder, etc.).

## Quick start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd eag-cognitive-agent
cp .env.example .env
# Edit .env — add GEMINI_API_KEY (and optional TAVILY_API_KEY)

uv sync
```

### 2. Start the LLM Gateway (separate terminal)

```bash
cd path/to/llm_gatewayV3
./run.sh
# Listens on http://localhost:8101
```

### 3. Run the agent

Clean runtime state before most presets (skip between `c1` and `c2` so memory persists):

```bash
rm -rf state workspace && mkdir -p state workspace
```

Single preset:

```bash
uv run python agent6.py --preset a
uv run python agent6.py --query "Your question here"
```

All course target queries (logged to `logs/`):

```bash
./scripts/run_all_queries.sh
```

Presets: **a** (Shannon Wikipedia), **b** (Tokyo + weather), **c1** (remember birthday + reminders), **c2** (recall birthday), **d** (asyncio synthesis).

### 4. Tests

```bash
uv run pytest
```

## Environment variables

| Variable | Default | Notes |
|----------|---------|--------|
| `LLM_GATEWAY_V3_URL` | `http://localhost:8101` | Preferred gateway |
| `LLM_GATEWAY_V2_URL` | `http://localhost:8100` | Fallback |
| `TAVILY_API_KEY` | — | Optional; improves `web_search` when DDG is rate-limited |
| `GEMINI_API_KEY` | — | Required for gateway (set in `.env` or gateway folder) |

Provider keys are read by the gateway from this project's `.env` and/or the gateway's own `.env`.

## Project layout

```
eag-cognitive-agent/
├── agent6.py              # Main loop + CLI
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
├── state/                 # gitignored — memory + artifacts
├── workspace/             # gitignored — agent file I/O
└── logs/                  # gitignored — run logs from scripts
```

## Git hygiene (no secrets)

These paths are **never** committed (see `.gitignore`):

- `.env` and any `.env.*` except `.env.example`
- `state/`, `workspace/`, `logs/`
- `llm_gatewayV3/`, `.venv/`, `__MACOSX/`

Safe to commit: source code, `prompts/`, `tests/`, `docs/`, `pyproject.toml`, `uv.lock`, `.env.example`.

```bash
cp .env.example .env   # then add keys locally only
./scripts/check-no-secrets.sh
git add -A && git status   # confirm .env does not appear
```

If `.env` was ever pushed, rotate all keys and remove it from history before sharing the repo.

## License

See [LICENSE](LICENSE).
