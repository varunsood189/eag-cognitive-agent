"""
Session 6 MCP server — nine tools over stdio.

Requires: ddgs, crawl4ai (optional), tavily (optional), .env with keys as needed.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).resolve().parent / ".env")

mcp = FastMCP("Session6AgentServer")

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE = BASE_DIR / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)


def _safe_path(rel: str) -> Path:
    candidate = (WORKSPACE / rel).resolve()
    if WORKSPACE not in candidate.parents and candidate != WORKSPACE:
        raise ValueError("path escapes workspace sandbox")
    return candidate


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web. Returns JSON list of {title, url, snippet}."""
    results: list[dict[str, str]] = []
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", r.get("link", "")),
                        "snippet": r.get("body", r.get("snippet", "")),
                    }
                )
    except Exception as e:
        results.append({"error": f"ddgs failed: {e}"})

    if not results and os.getenv("TAVILY_API_KEY"):
        try:
            from tavily import TavilyClient

            tv = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
            resp = tv.search(query=query, max_results=max_results)
            for r in resp.get("results", []):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                    }
                )
        except Exception as e:
            results.append({"error": f"tavily failed: {e}"})

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
        target = _safe_path(path)
    if not target.exists():
        return json.dumps({"error": "file not found", "path": path})
    return target.read_text(encoding="utf-8", errors="replace")


@mcp.tool()
def list_dir(path: str = ".") -> str:
    """List directory under workspace/ or state/."""
    if path.startswith("state/"):
        target = (STATE_DIR / path[6:]).resolve()
    elif path in (".", ""):
        target = WORKSPACE
    else:
        target = _safe_path(path)
    if not target.exists():
        return json.dumps({"error": "not found", "path": path})
    entries = []
    for p in sorted(target.iterdir()):
        entries.append({"name": p.name, "type": "dir" if p.is_dir() else "file"})
    return json.dumps({"path": str(target), "entries": entries})


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


if __name__ == "__main__":
    mcp.run(transport="stdio")
