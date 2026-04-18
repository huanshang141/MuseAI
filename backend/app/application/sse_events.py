"""SSE (Server-Sent Events) payload builders.

Two schemas coexist and are pinned by frontend consumers:

1. Chat schema — used by `chat_stream_service` and consumed by
   `frontend/src/composables/useChat.js`. Flat payload keyed by "type":
   `{"type": <name>, <extra-fields>}`.

2. Tour schema — used by `tour_chat_service` and consumed by
   `frontend/src/composables/useTour.js`. Keyed by "event":
   `{"event": <name>, "data": {...}}` for most events, or
   `{"event": "done", <flat-fields>}` for the done event (intentional
   inconsistency — matches the current wire format).

Do NOT unify the two schemas here. Changing field names would silently
break the frontend.

The builders accept `**kwargs` so callers can add arbitrary extra fields
without the module needing to know every variant up-front. Kwarg insertion
order is preserved in the JSON output (Python ≥3.7 dict order guarantee).
"""
import json
from typing import Any


def sse_chat_event(type_: str, **fields: Any) -> str:
    payload: dict[str, Any] = {"type": type_}
    payload.update(fields)
    return f"data: {json.dumps(payload)}\n\n"


def sse_tour_event(event_: str, **fields: Any) -> str:
    payload: dict[str, Any] = {"event": event_}
    payload.update(fields)
    return f"data: {json.dumps(payload)}\n\n"
