# Rendering inquiry checklist (before adding SYSTEM rules)

When a role loops, hallucinates, or picks the wrong tool, **do not** add a rule to that role’s SYSTEM prompt as the first move.

## 1. Reconstruct what the role saw

Trace the code path from typed objects → prompt string:

| Role | Builder | Prompt file |
|------|---------|-------------|
| Perception | `perception.observe()` | `prompts/perception_system.txt` |
| Decision | `decision.next_step()` | `prompts/decision_system.txt` |

Include everything rendered into the user message:

- MEMORY HITS → `prompt_render.format_memory_hits*` in `prompt_render.py`
- RUN HISTORY / RECENT HISTORY → `agent7.py` history + `summarize_action_result()`
- ATTACHED ARTIFACTS → `decision._format_attached()` / `_excerpt_artifact()`
- MCP tools list → gateway from `session.list_tools()`

## 2. Ask the diagnostic question

**Did the role behave rationally given that visible input?**

- **Yes** → fix SYSTEM prompt or model/routing; rendering is likely fine.
- **No** (information was missing or truncated) → fix **upstream rendering** in `prompt_render.py`, `memory.record_outcome()`, or `agent7` history — not a new “don’t loop” rule.

## 3. Session 7 examples (fixed in rendering)

| Symptom | Wrong fix | Actual cause | Fix location |
|---------|-----------|--------------|--------------|
| c2: Decision can’t see mom’s birthday date | “Answer from memory when date present” | `_format_hits` dropped `value.raw` | `prompt_render.py` → `raw:` line |
| g/h: `search_knowledge` loop | “Never call same tool twice” | Hits showed descriptors only; chunk text hidden | `chunk:` + `search results:` in `format_memory_hits`; history via `summarize_action_result()` |

## 4. After a rendering fix

1. Re-run the failing preset.
2. `./scripts/check-perception-gate.sh` (Perception still intent-only).
3. `uv run pytest tests/test_prompt_render.py -q`

## 5. When a SYSTEM rule *is* appropriate

Tool **choice** mapping (e.g. `index_directory` for “every .md under papers/”) belongs in Decision SYSTEM + MCP docstrings — Perception must not name tools.

Bulk ingest intent (“every .md under papers/”) belongs as **one Perception goal**, not one goal per file — Decision maps that to `index_directory`.

Do not duplicate the same policy in `decision.py` `_goal_hints`; use `RUN CONTEXT` for dynamic facts only (e.g. URLs already fetched).
