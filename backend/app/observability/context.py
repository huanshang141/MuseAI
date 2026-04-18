"""Request-scoped ContextVars for cross-layer log correlation.

RequestLoggingMiddleware sets request_id_var at request entry. Any async
code executing within that request (including async generators used by
SSE streaming) can read it and bind it to log records via
`logger.bind(request_id=request_id_var.get())`.

ContextVar is the right primitive here because:
- values propagate automatically through asyncio.create_task and async
  generators (unlike plain module globals, which would leak between
  concurrent requests).
- reset() on task exit restores the previous value, so nested requests
  (none in our code today, but future-proof) work correctly.
"""
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
