"""Action layer — pure MCP dispatch, artifact threshold, art: guard."""

from __future__ import annotations

from mcp import ClientSession

from artifacts import ARTIFACT_THRESHOLD_BYTES, ArtifactStore
from schemas import ToolCall

artifact_store = ArtifactStore()


def _collapse_result(result) -> str:
    parts: list[str] = []
    for block in result.content or []:
        if hasattr(block, "text") and block.text:
            parts.append(block.text)
        elif hasattr(block, "data"):
            parts.append(str(block.data))
    return "\n".join(parts) if parts else ""


def _has_art_handle(arguments: dict) -> bool:
    for key in ("path", "url", "filename", "file_path"):
        val = arguments.get(key)
        if isinstance(val, str) and val.strip().startswith("art:"):
            return True
    return False


async def execute(
    session: ClientSession,
    tool_call: ToolCall,
) -> tuple[str, str | None]:
    if _has_art_handle(tool_call.arguments):
        msg = (
            "ERROR: artifact handles (art:...) are not valid MCP paths or URLs. "
            "Read attached artifact bytes from the Decision prompt instead."
        )
        return msg, None

    result = await session.call_tool(tool_call.name, arguments=tool_call.arguments)
    text = _collapse_result(result)
    raw = text.encode("utf-8", errors="replace")

    if len(raw) > ARTIFACT_THRESHOLD_BYTES:
        art_id = artifact_store.put(
            raw,
            content_type="text/plain",
            source=f"mcp:{tool_call.name}",
            descriptor=f"{tool_call.name}({tool_call.arguments})",
        )
        preview = text[:400].replace("\n", " ")
        descriptor = f"[artifact {art_id}, {len(raw)} bytes] preview: {preview}"
        return descriptor, art_id

    return text, None
