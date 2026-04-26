from __future__ import annotations

import json
from typing import Any

_MAX_LEN = 8000
_TRUNCATED = "\n... [truncated]"


def _truncate(text: str, max_len: int = _MAX_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + _TRUNCATED


def to_readable_request(masked_payload: dict[str, Any] | None) -> str:
    if not masked_payload:
        return "[No request payload]"
    lines: list[str] = []
    model = masked_payload.get("model") or "unknown"
    lines.append(f"Model: {model}")
    messages = masked_payload.get("messages")
    if messages:
        lines.append("Messages:")
        for idx, msg in enumerate(messages, start=1):
            role = msg.get("role", "unknown") if isinstance(msg, dict) else "unknown"
            content = ""
            if isinstance(msg, dict):
                content = msg.get("content") or ""
                if isinstance(content, list):
                    content = json.dumps(content, ensure_ascii=False)
            lines.append(f"  {idx}. [{role}] {content}")
    prompt = masked_payload.get("prompt")
    if prompt:
        lines.append(f"Prompt:\n  {prompt}")
    for key in ("temperature", "max_tokens", "top_p"):
        val = masked_payload.get(key)
        if val is not None:
            lines.append(f"{key}: {val}")
    return _truncate("\n".join(lines))


def to_readable_response(masked_payload: dict[str, Any] | None) -> str:
    if not masked_payload:
        return "[No response payload]"
    lines: list[str] = []
    choices = masked_payload.get("choices")
    if choices and isinstance(choices, list):
        for idx, choice in enumerate(choices, start=1):
            if isinstance(choice, dict):
                content = ""
                message = choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content") or ""
                else:
                    content = choice.get("text") or ""
                lines.append(f"  {idx}. {content}")
    text = masked_payload.get("text")
    if text:
        lines.append(f"Text: {text}")
    content = masked_payload.get("content")
    if content:
        lines.append(f"Content: {content}")
    usage = masked_payload.get("usage")
    if isinstance(usage, dict):
        lines.append(
            f"Usage: prompt={usage.get('prompt_tokens', '?')}, "
            f"completion={usage.get('completion_tokens', '?')}, "
            f"total={usage.get('total_tokens', '?')}"
        )
    return _truncate("\n".join(lines))
