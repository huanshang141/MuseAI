"""Pins the SSE wire protocols used by chat_stream_service and tour_chat_service.

Frontend consumers (useChat.js, useTour.js) parse events by exact field name.
If anyone accidentally renames "type" → "event" (or vice versa) in a refactor,
this test fails loudly instead of silently breaking the frontend.

Also guards against the return of inline json.dumps(...) SSE literals now
that sse_events.py exists — the only approved way to produce SSE payloads
from these services is via the builders.
"""
import re
from pathlib import Path

CHAT_SERVICE = Path(__file__).resolve().parents[2] / "app" / "application" / "chat_stream_service.py"
TOUR_SERVICE = Path(__file__).resolve().parents[2] / "app" / "application" / "tour_chat_service.py"


def test_chat_stream_service_has_no_raw_json_dumps_sse_literals():
    source = CHAT_SERVICE.read_text(encoding="utf-8")
    assert "json.dumps" not in source, (
        "chat_stream_service.py must not construct SSE payloads via json.dumps. "
        "Use sse_chat_event() from app.application.sse_events."
    )


def test_tour_chat_service_has_no_raw_json_dumps_sse_literals():
    source = TOUR_SERVICE.read_text(encoding="utf-8")
    assert "json.dumps" not in source, (
        "tour_chat_service.py must not construct SSE payloads via json.dumps. "
        "Use sse_tour_event() from app.application.sse_events."
    )


def test_chat_service_uses_type_keyed_events_only():
    source = CHAT_SERVICE.read_text(encoding="utf-8")
    assert "sse_chat_event" in source
    assert "sse_tour_event" not in source, (
        "chat_stream_service uses the 'type'-keyed schema — sse_tour_event belongs in tour_chat_service."
    )


def test_tour_service_uses_event_keyed_events_only():
    source = TOUR_SERVICE.read_text(encoding="utf-8")
    assert "sse_tour_event" in source
    assert "sse_chat_event" not in source, (
        "tour_chat_service uses the 'event'-keyed schema — sse_chat_event belongs in chat_stream_service."
    )


def test_sse_events_builders_produce_expected_key_names():
    from app.application.sse_events import sse_chat_event, sse_tour_event

    chat_output = sse_chat_event("chunk", stage="generate", content="x")
    assert re.match(r'^data: \{"type": "chunk"', chat_output), (
        f"sse_chat_event must emit 'type'-keyed payload, got: {chat_output!r}"
    )

    tour_output = sse_tour_event("chunk", data={"content": "x"})
    assert re.match(r'^data: \{"event": "chunk"', tour_output), (
        f"sse_tour_event must emit 'event'-keyed payload, got: {tour_output!r}"
    )
