"""LLM Gateway V7 client (V2-compatible fallback)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

V7_URL = os.getenv("LLM_GATEWAY_V7_URL", "http://localhost:8107")
V2_URL = os.getenv("LLM_GATEWAY_V2_URL", "http://localhost:8100")


def _find_gateway_client_dir() -> Path | None:
    here = Path(__file__).resolve().parent
    candidates = [
        here / "llm_gatewayV7",
        here.parent / "llm_gatewayV7",
        here.parent / "Assignment 5" / "71c832d6-d71c-40e4-9912-fa26c61addba" / "llm_gatewayV2",
        here.parent / "llm_gatewayV2",
    ]
    for c in candidates:
        if (c / "client.py").exists():
            return c
    return None


def _import_course_llm() -> type | None:
    gw_dir = _find_gateway_client_dir()
    if gw_dir is None:
        return None
    sys.path.insert(0, str(gw_dir))
    try:
        from client import LLM as CourseLLM  # type: ignore

        return CourseLLM
    except ImportError:
        return None


class GatewayClient:
    """HTTP client for gateway /v1/chat with auto_route (V7) or provider override (V2)."""

    def __init__(self) -> None:
        self._course_llm_cls = _import_course_llm()
        self._v7_ok: bool | None = None
        self._active_url = V7_URL

    def _probe(self, url: str) -> bool:
        try:
            r = httpx.get(f"{url.rstrip('/')}/v1/capabilities", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False

    def ensure_gateway(self) -> str:
        if self._v7_ok is None:
            if self._probe(V7_URL):
                self._v7_ok = True
                self._active_url = V7_URL
            elif self._probe(V2_URL):
                self._v7_ok = False
                self._active_url = V2_URL
            else:
                raise RuntimeError(
                    f"No LLM gateway reachable at {V7_URL} or {V2_URL}. "
                    "Start llm_gatewayV7 (port 8107) or llm_gatewayV2 (port 8100)."
                )
        return self._active_url

    def chat(self, **kwargs: Any) -> dict:
        url = self.ensure_gateway()
        auto_route = kwargs.pop("auto_route", None)
        provider = kwargs.pop("provider", None)

        # V2 has no router pool — map auto_route to provider hints
        if not self._v7_ok and auto_route:
            if auto_route in ("perception", "memory"):
                provider = provider or "g"
            # decision: leave provider None for failover

        body = {k: v for k, v in kwargs.items() if v is not None}
        if auto_route and self._v7_ok:
            body["auto_route"] = auto_route
        if provider:
            body["provider"] = provider

        import re
        import time

        def _backoff_sleep(exc: httpx.HTTPStatusError, attempt: int) -> None:
            wait = 2**attempt
            try:
                detail = exc.response.json().get("detail", "")
                text = detail if isinstance(detail, str) else str(detail)
                m = re.search(r"backoff.*?(\d+)s left", text, re.I)
                if m:
                    wait = int(m.group(1)) + 2
            except Exception:
                pass
            time.sleep(min(wait, 90))

        last_exc: httpx.HTTPStatusError | None = None
        for attempt in range(6):
            try:
                if self._course_llm_cls is not None:
                    llm = self._course_llm_cls(base_url=url)
                    return llm.chat(**body)

                r = httpx.post(f"{url.rstrip('/')}/v1/chat", json=body, timeout=600.0)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in (502, 503) and attempt < 5:
                    _backoff_sleep(exc, attempt)
                    continue
                break

        if last_exc is not None:
            detail = ""
            try:
                detail = last_exc.response.json().get("detail", "")
            except Exception:
                detail = last_exc.response.text[:500]
            raise RuntimeError(
                f"Gateway {last_exc.response.status_code} for /v1/chat "
                f"(provider={provider!r}, auto_route={auto_route!r}): {detail}"
            ) from last_exc
        raise RuntimeError("gateway chat failed with no response")


_gateway: GatewayClient | None = None


def get_gateway() -> GatewayClient:
    global _gateway
    if _gateway is None:
        _gateway = GatewayClient()
    return _gateway


def ensure_gateway() -> None:
    get_gateway().ensure_gateway()


def gateway_chat(**kwargs: Any) -> dict:
    return get_gateway().chat(**kwargs)


def response_format_from_model(model: type) -> dict:
    schema = model.model_json_schema()
    return {
        "type": "json_schema",
        "schema": schema,
        "name": model.__name__,
        "strict": True,
    }


def embed(text: str, task_type: str = "retrieval_document") -> dict:
    """Call V7 POST /v1/embed. Returns {embedding, dim, model, provider, ...}."""
    url = get_gateway().ensure_gateway()
    if not url.rstrip("/").endswith("8107") and V7_URL not in url:
        # Embed exists only on V7; probe V7 directly.
        if get_gateway()._probe(V7_URL):
            url = V7_URL
        else:
            raise RuntimeError(
                f"Embedding requires LLM Gateway V7 at {V7_URL}. "
                "Start llm_gatewayV7 (./run.sh) with Ollama nomic-embed-text."
            )
    body = {"text": text, "task_type": task_type}
    if get_gateway()._course_llm_cls is not None:
        llm = get_gateway()._course_llm_cls(base_url=url)
        return llm.embed(text, task_type=task_type)
    r = httpx.post(f"{url.rstrip('/')}/v1/embed", json=body, timeout=120.0)
    r.raise_for_status()
    return r.json()


def parse_structured(reply: dict, model: type):
    if reply.get("parsed"):
        return model.model_validate(reply["parsed"])
    text = reply.get("text") or ""
    try:
        return model.model_validate(json.loads(text))
    except Exception:
        import re

        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return model.model_validate(json.loads(m.group(0)))
        raise
