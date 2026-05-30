"""Part 2 custom queries (verbatim for README and traces)."""

from __future__ import annotations

CUSTOM_QUERIES: dict[str, str] = {
    "q1": (
        "Which roles offer strong pay for people who never manage staff and "
        "focus on hands-on modeling work?"
    ),
    "q2": (
        "Where can someone work fully from home in machine learning and still "
        "earn above two hundred thousand dollars?"
    ),
    "q3": (
        "What jobs suit someone at the very beginning of their career outside "
        "the United States?"
    ),
    "q4": (
        "What is the highest listed compensation for a position centered on "
        "natural language processing or large language models?"
    ),
    "q5": (
        "How does typical pay for AI engineers compare to data scientists when "
        "both are based in the United Kingdom?"
    ),
}

# agent7 preset aliases
AGENT_PRESETS = {f"j{i}": q for i, (k, q) in enumerate(CUSTOM_QUERIES.items(), start=1)}

QUERY_META = {
    "q1": {"type": "semantic", "notes": "IC / individual contributor; query avoids 'individual contributor'"},
    "q2": {"type": "semantic", "notes": "remote ML >200k; query says 'from home' not 'remote'"},
    "q3": {"type": "semantic", "notes": "entry outside US; query avoids 'junior'/'entry'"},
    "q4": {"type": "factual", "notes": "max NLP/LLM compensation"},
    "q5": {"type": "comparison", "notes": "UK AI engineer vs data scientist pay"},
}
