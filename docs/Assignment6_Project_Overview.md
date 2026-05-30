# Assignment 6 — Agentic Architecture (Simple Overview)

**EAG V3 Session 6** | Four-role cognitive agent with MCP tools and LLM Gateway

---

## What this project is

A Python agent that answers multi-step questions by splitting work into **four roles**, each with one clear job. It does not use LangChain or a single giant prompt. Every step uses **typed data** (Pydantic models) and an **LLM Gateway** for all AI calls.

---

## The four roles

| Role | Job | Uses LLM? |
|------|-----|-----------|
| **Memory** | Remember facts, tool results, preferences; search them later | Only when classifying new text |
| **Perception** | Split the user question into goals; mark goals done; attach big files when needed | Yes (Gemini) |
| **Decision** | Work on **one goal at a time**: answer OR call one MCP tool | Yes |
| **Action** | Run the MCP tool (search, fetch URL, files, etc.) | No |

**Rule:** Decision never sees the full goal list—only the current goal.

---

## How one run works

```
User question
    → Memory remembers the query
    → Loop until all goals done:
         Memory: what do we already know?
         Perception: update goal list (open / done / attach file?)
         Decision: next step for first open goal
         Action: call tool OR skip if Decision answered
    → Final answer from history
```

Large web pages are stored as **artifacts** (`art:...`). Memory keeps a short handle; Decision gets the full text only when Perception attaches it.

---

## Main files

| File | Purpose |
|------|---------|
| `agent7.py` | Main loop and CLI |
| `schemas.py` | Data shapes between roles |
| `memory.py` | Persistent `state/memory.json` |
| `perception.py` | Goal list and done flags |
| `decision.py` | One tool or one answer per step |
| `action.py` | MCP dispatch |
| `mcp_server.py` | Nine tools (search, fetch, files, time, …) |
| `gateway.py` | Talks to LLM Gateway V7 on port 8107 |
| `artifacts.py` | Big files under `state/artifacts/` |

---

## Assignment queries (presets)

| Preset | What it tests |
|--------|----------------|
| **a** | Fetch Wikipedia → extract facts (artifact attach) |
| **b** | Search + weather + pick best option (memory across goals) |
| **c1** | Remember birthday, create reminder files |
| **c2** | Same `state/` — recall birthday from memory |
| **d** | Search, read top pages, synthesize a list |

Run: `uv run python agent7.py --preset a` (and b, c1, c2, d).

---

## What you need to run

1. **Python 3.11+** and **uv** — `uv sync` in project folder  
2. **`.env`** — at least `GEMINI_API_KEY`  
3. **LLM Gateway V7** running — `cd llm_gatewayV7 && ./run.sh` (port 8107)  
4. **Clean state** before most presets: `rm -rf state workspace && mkdir -p state workspace`  
   - **Exception:** do not delete `state/` before preset **c2** if you already ran **c1**

---

## One-line summary

**Perception plans goals, Decision acts on one goal at a time, Action runs tools, Memory connects everything—and the loop repeats until Perception says all goals are done.**

---

*School of AI — Assignment 6*
