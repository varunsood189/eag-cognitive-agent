"""
Session 7 MCP server — eleven tools over stdio.

web_search:        Tavily primary, DuckDuckGo fallback (usage.json cap).
fetch_url:         Wikipedia API + httpx; crawl4ai fallback for other URLs.
index_document:    Chunk one workspace file or artifact into FAISS-backed Memory.
index_directory: Index every matching file under a workspace directory.
search_knowledge:  Vector search over indexed fact chunks.

File tools are sandboxed under workspace/.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

import indexing
import memory as _memory
from artifacts import ArtifactStore

load_dotenv(Path(__file__).resolve().parent / ".env")

mcp = FastMCP("Session7AgentServer")

BASE_DIR = Path(__file__).resolve().parent
PAPERS_REPO = BASE_DIR / "papers"
WORKSPACE = BASE_DIR / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_course_papers_in_workspace() -> None:
    """Copy tracked repo papers/ into workspace/papers/ for MCP file tools."""
    if not PAPERS_REPO.is_dir():
        return
    dest = WORKSPACE / "papers"
    dest.mkdir(parents=True, exist_ok=True)
    for md in PAPERS_REPO.glob("*.md"):
        shutil.copy2(md, dest / md.name)


_ensure_course_papers_in_workspace()


def _resolve_read_path(rel: str) -> Path:
    """Resolve a path under workspace/; fall back to repo papers/ if needed."""
    rel = rel.lstrip("/")
    ws = (WORKSPACE / rel).resolve()
    if ws.is_file():
        return ws
    if rel.startswith("papers/"):
        repo_file = (PAPERS_REPO / rel[len("papers/") :]).resolve()
        if repo_file.is_file():
            return repo_file
    return _safe_path(rel)

USAGE_PATH = BASE_DIR / "usage.json"
MAX_SEARCH_RESULTS = 5
MONTHLY_CAP = 950
_usage_lock = threading.Lock()


def _safe_path(rel: str) -> Path:
    candidate = (WORKSPACE / rel).resolve()
    if WORKSPACE not in candidate.parents and candidate != WORKSPACE:
        raise ValueError("path escapes workspace sandbox")
    return candidate


def _empty_usage(month: str) -> dict:
    return {
        "month": month,
        "tavily": {"count": 0, "errors": 0},
        "duckduckgo": {"count": 0, "errors": 0},
    }


def _load_usage() -> dict:
    month = datetime.now().strftime("%Y-%m")
    if not USAGE_PATH.exists():
        return _empty_usage(month)
    try:
        data = json.loads(USAGE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_usage(month)
    if data.get("month") != month:
        return _empty_usage(month)
    for key in ("tavily", "duckduckgo"):
        data.setdefault(key, {"count": 0, "errors": 0})
    return data


def _save_usage(data: dict) -> None:
    USAGE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _bump(provider: str, field: str = "count") -> None:
    with _usage_lock:
        data = _load_usage()
        data[provider][field] = data[provider].get(field, 0) + 1
        _save_usage(data)


def _under_cap(provider: str) -> bool:
    return _load_usage()[provider]["count"] < MONTHLY_CAP


def _tavily_search(query: str, max_results: int) -> list[dict]:
    from tavily import TavilyClient

    client = TavilyClient(os.environ["TAVILY_API_KEY"])
    resp = client.search(query=query, max_results=max_results, search_depth="advanced")
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        }
        for r in resp.get("results", [])
    ]


def _ddg_search(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS

    hits: list[dict] = []
    with DDGS() as ddgs:
        for backend in ("auto", "html", "lite"):
            try:
                hits = list(ddgs.text(query, max_results=max_results, backend=backend))
            except Exception:
                hits = []
            if hits:
                break
    return [
        {
            "title": h.get("title", ""),
            "url": h.get("href", h.get("link", "")),
            "snippet": h.get("body", h.get("snippet", "")),
        }
        for h in hits
    ]


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web (Tavily primary, DDG fallback). Hard-capped at 5 results."""
    max_results = max(1, min(max_results, MAX_SEARCH_RESULTS))
    results: list[dict] = []
    if os.getenv("TAVILY_API_KEY") and _under_cap("tavily"):
        try:
            results = _tavily_search(query, max_results)
            if results:
                _bump("tavily")
                return json.dumps(results, ensure_ascii=True)
        except Exception:
            _bump("tavily", "errors")
    results = _ddg_search(query, max_results)
    _bump("duckduckgo")
    return json.dumps(results, ensure_ascii=True)


_BROWSER_HEADERS = {
    "User-Agent": "EAGCognitiveAgent/1.0 (schoolofai; educational)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_wikipedia_api(url: str) -> str:
    """Fetch Wikipedia via REST summary + parse API (curl fallback if httpx blocked)."""
    import subprocess
    from urllib.parse import unquote

    import httpx

    m = re.search(r"wikipedia\.org/wiki/([^?#]+)", url, re.I)
    if not m:
        return ""
    title = unquote(m.group(1)).replace(" ", "_")
    ua = _BROWSER_HEADERS["User-Agent"]

    def _curl_get(target: str) -> str:
        proc = subprocess.run(
            ["curl", "-sL", "-A", ua, target],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[:300] or f"curl exit {proc.returncode}")
        return proc.stdout

    rest_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    try:
        raw = _curl_get(rest_url)
        data = json.loads(raw)
        parts = [data.get("title", ""), data.get("description", ""), data.get("extract", "")]
        summary = "\n\n".join(p for p in parts if p)
        if len(summary) > 800:
            return summary
    except Exception:
        pass

    parse_url = (
        "https://en.wikipedia.org/w/api.php?"
        f"action=parse&page={title}&prop=text&format=json&formatversion=2"
    )
    try:
        raw = _curl_get(parse_url)
        html = json.loads(raw).get("parse", {}).get("text", "")
        if html:
            return _html_to_text(html)
    except Exception:
        pass

    r = httpx.get(rest_url, headers=_BROWSER_HEADERS, timeout=45.0)
    r.raise_for_status()
    data = r.json()
    return "\n\n".join(
        p for p in (data.get("title", ""), data.get("description", ""), data.get("extract", "")) if p
    )


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@mcp.tool()
def fetch_url(url: str) -> str:
    """Fetch a URL and return cleaned markdown/text content."""
    if url.strip().startswith("art:"):
        return json.dumps({"error": "artifact handles are not URLs"})

    url = url.strip()
    text = ""

    if "wikipedia.org/wiki/" in url.lower():
        try:
            text = _fetch_wikipedia_api(url)
        except Exception as e:
            return json.dumps({"error": f"wikipedia api: {e}", "url": url})

    if not text.strip():
        try:
            import httpx

            r = httpx.get(
                url,
                timeout=30.0,
                follow_redirects=True,
                headers=_BROWSER_HEADERS,
            )
            r.raise_for_status()
            text = _html_to_text(r.text)
        except Exception as e:
            return json.dumps({"error": str(e), "url": url})

    if not text.strip():
        return json.dumps({"error": "empty page content", "url": url})

    return text[:500_000]


@mcp.tool()
def get_time(timezone_name: str = "UTC") -> str:
    """Return current ISO datetime for a timezone (e.g. Asia/Tokyo, UTC)."""
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = timezone.utc
    now = datetime.now(tz)
    return json.dumps(
        {
            "timezone": timezone_name,
            "iso": now.isoformat(),
            "weekday": now.strftime("%A"),
        }
    )


@mcp.tool()
def currency_convert(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert amount between currencies using a public rate API."""
    import httpx

    fr, to = from_currency.upper(), to_currency.upper()
    try:
        r = httpx.get(
            f"https://api.frankfurter.app/latest?from={fr}&to={to}",
            timeout=15.0,
        )
        r.raise_for_status()
        rate = r.json()["rates"][to]
        converted = round(amount * rate, 4)
        return json.dumps(
            {
                "amount": amount,
                "from": fr,
                "to": to,
                "rate": rate,
                "converted": converted,
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def read_file(path: str) -> str:
    """Read a file under workspace/ or state/."""
    if path.startswith("art:"):
        return json.dumps({"error": "use attached artifacts, not art: paths"})
    if path.startswith("state/"):
        target = (STATE_DIR / path[6:]).resolve()
        if STATE_DIR not in target.parents and target != STATE_DIR:
            raise ValueError("invalid state path")
    else:
        target = _resolve_read_path(path)
    if not target.exists():
        return json.dumps({"error": "file not found", "path": path})
    return target.read_text(encoding="utf-8", errors="replace")


@mcp.tool()
def list_dir(path: str = ".") -> str:
    """List directory under workspace/ or state/. Returns count + names (S7 shape)."""
    if path.startswith("state/"):
        target = (STATE_DIR / path[6:]).resolve()
    elif path in (".", ""):
        _ensure_course_papers_in_workspace()
        target = WORKSPACE
    else:
        if path == "papers" or path.startswith("papers/"):
            _ensure_course_papers_in_workspace()
        target = _safe_path(path)
    if not target.exists():
        return json.dumps({"error": "not found", "path": path})
    entries = []
    names: list[str] = []
    for p in sorted(target.iterdir()):
        is_dir = p.is_dir()
        entries.append({
            "name": p.name,
            "type": "dir" if is_dir else "file",
            "size_bytes": 0 if is_dir else p.stat().st_size,
        })
        names.append(p.name)
    return json.dumps({
        "path": path,
        "count": len(entries),
        "names": names,
        "entries": entries,
    })


@mcp.tool()
def create_file(path: str, content: str) -> str:
    """Create a new file under workspace/ or state/."""
    if path.startswith("state/"):
        target = (STATE_DIR / path[6:]).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        target = _safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return json.dumps({"error": "file exists", "path": path})
    target.write_text(content, encoding="utf-8")
    return json.dumps({"ok": True, "path": path, "bytes": len(content.encode())})


@mcp.tool()
def update_file(path: str, content: str) -> str:
    """Overwrite a file under workspace/ or state/."""
    if path.startswith("state/"):
        target = (STATE_DIR / path[6:]).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        target = _safe_path(path)
    target.write_text(content, encoding="utf-8")
    return json.dumps({"ok": True, "path": path, "bytes": len(content.encode())})


@mcp.tool()
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace first occurrence of old_text with new_text in a file."""
    if path.startswith("state/"):
        target = (STATE_DIR / path[6:]).resolve()
    else:
        target = _safe_path(path)
    if not target.exists():
        return json.dumps({"error": "file not found"})
    body = target.read_text(encoding="utf-8")
    if old_text not in body:
        return json.dumps({"error": "old_text not found"})
    target.write_text(body.replace(old_text, new_text, 1), encoding="utf-8")
    return json.dumps({"ok": True, "path": path})


# ── document indexing (Session 7) ─────────────────────────────────────────


_artifact_store = ArtifactStore()


def _read_for_index(path: str) -> tuple[str, str]:
    if path.startswith("art:"):
        blob = _artifact_store.get_bytes(path)
        return blob.decode("utf-8", errors="replace"), path
    _ensure_course_papers_in_workspace()
    p = _resolve_read_path(path)
    if not p.is_file():
        raise FileNotFoundError(f"No such file: {path} (looked under workspace/ and papers/)")
    return p.read_text(encoding="utf-8"), f"workspace:{path}"


def _index_one_file(
    path: str,
    *,
    chunk_size: int,
    overlap: int,
    run_id: str,
) -> dict:
    text, source = _read_for_index(path)
    if not text.strip():
        return {"path": path, "source": source, "chunks_indexed": 0, "warning": "empty content"}
    n = indexing.index_text(
        _memory.memory,
        text,
        source,
        run_id=run_id,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    return {
        "path": path,
        "source": source,
        "chunks_indexed": n,
        "chunk_size": chunk_size,
        "overlap": overlap,
    }


@mcp.tool()
def index_document(path: str, chunk_size: int = 400, overlap: int = 80) -> str:
    """Chunk one workspace file or artifact into Memory as searchable facts. Use for a single known path like papers/attention.md. For indexing every .md in a folder, use index_directory instead. For one-shot read-only inspection, use read_file."""
    if path.endswith("/.md") or path in (".md", "papers/.md"):
        return json.dumps(
            {
                "error": f"invalid path {path!r}; use papers/<filename>.md or index_directory('papers')",
                "chunks_indexed": 0,
            }
        )
    run_id = f"index-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    try:
        result = _index_one_file(path, chunk_size=chunk_size, overlap=overlap, run_id=run_id)
    except FileNotFoundError as e:
        return json.dumps({"path": path, "error": str(e), "chunks_indexed": 0})
    return json.dumps(result)


@mcp.tool()
def index_directory(
    directory: str = "papers",
    pattern: str = "*.md",
    chunk_size: int = 400,
    overlap: int = 80,
) -> str:
    """Index every file matching pattern under a workspace directory (e.g. all papers/*.md). Returns per-file chunk counts and a total. Use when the goal is to index an entire corpus folder, not a single file."""
    _ensure_course_papers_in_workspace()
    if directory.startswith("state/"):
        root = (STATE_DIR / directory[6:]).resolve()
    else:
        root = _safe_path(directory)
    if not root.is_dir():
        return json.dumps({"error": f"not a directory: {directory}", "total_chunks_indexed": 0})

    run_id = f"index-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    per_file: list[dict] = []
    total = 0
    for file_path in sorted(root.glob(pattern)):
        if not file_path.is_file():
            continue
        rel = str(file_path.relative_to(WORKSPACE)).replace("\\", "/")
        try:
            one = _index_one_file(rel, chunk_size=chunk_size, overlap=overlap, run_id=run_id)
            n = int(one.get("chunks_indexed") or 0)
            total += n
            per_file.append(one)
        except FileNotFoundError as e:
            per_file.append({"path": rel, "error": str(e), "chunks_indexed": 0})

    return json.dumps(
        {
            "directory": directory,
            "pattern": pattern,
            "files_indexed": len(per_file),
            "total_chunks_indexed": total,
            "per_file": per_file,
        }
    )


@mcp.tool()
def search_knowledge(query: str, k: int = 5) -> str:
    """Vector search over indexed fact chunks. Call when Memory already contains indexed chunks for the topic rather than re-fetching URLs or re-reading source files."""
    items = _memory.read(query, kinds=["fact"], top_k=max(k * 4, 12))
    items = [
        item
        for item in items
        if (item.value or {}).get("chunk")
        or "[workspace:" in (item.descriptor or "")
        or "[corpus:" in (item.descriptor or "")
    ][:k]
    return json.dumps(
        [
            {
                "id": item.id,
                "descriptor": item.descriptor,
                "source": item.source,
                "chunk_preview": (item.value.get("chunk") or "")[:240],
                "metadata": {key: val for key, val in item.value.items() if key != "chunk"},
            }
            for item in items
        ]
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
