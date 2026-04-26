from __future__ import annotations

import contextvars
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

_trace_ctx: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("llm_trace_ctx", default=None)


@contextmanager
def set_trace_context(
    request_id: str | None = None,
    trace_id: str | None = None,
    source: str | None = None,
    endpoint_method: str | None = None,
    endpoint_path: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    session_type: str | None = None,
    session_id: str | None = None,
) -> Generator[None, None, None]:
    token = _trace_ctx.set(
        {
            "request_id": request_id,
            "trace_id": trace_id,
            "source": source,
            "endpoint_method": endpoint_method,
            "endpoint_path": endpoint_path,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "session_type": session_type,
            "session_id": session_id,
        }
    )
    try:
        yield
    finally:
        _trace_ctx.reset(token)


def get_trace_context() -> dict[str, Any]:
    val = _trace_ctx.get(None)
    return val.copy() if val is not None else {}
