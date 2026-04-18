"""Stream-behavior tests for ask_stream_tour.

Existing tests (test_tour_chat_service.py) only cover build_system_prompt.
This file adds coverage for the async generator itself, including the
regression test for PERFOPS-P1-02 (error-then-done dual emission bug).
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.tour_chat_service import ask_stream_tour


def _collect_event_types(events: list[str]) -> list[str]:
    parsed = []
    for raw in events:
        assert raw.startswith("data: ")
        assert raw.endswith("\n\n")
        payload = json.loads(raw[len("data: "):-2])
        parsed.append(payload.get("event"))
    return parsed


@pytest.fixture
def fake_tour_session():
    return SimpleNamespace(
        visited_exhibit_ids=[],
        persona="A",
        assumption="A",
        current_hall="relic-hall",
    )


@pytest.fixture
def fake_session_maker():
    session_ctx = AsyncMock()
    session_ctx.__aenter__.return_value = AsyncMock()
    session_ctx.__aexit__.return_value = None
    maker = MagicMock(return_value=session_ctx)
    return maker


@pytest.mark.asyncio
async def test_stream_emits_chunk_then_done_on_success(
    monkeypatch, fake_tour_session, fake_session_maker
):
    async def fake_get_session(db, sid):
        return fake_tour_session
    monkeypatch.setattr(
        "app.application.tour_chat_service.get_session", fake_get_session
    )
    async def fake_record_events(*args, **kwargs):
        return None
    monkeypatch.setattr(
        "app.application.tour_chat_service.record_events", fake_record_events
    )

    rag_agent = MagicMock()
    rag_agent.run = AsyncMock(return_value={"answer": "hello"})

    events = []
    async for event in ask_stream_tour(
        db_session=MagicMock(),
        session_maker=fake_session_maker,
        tour_session_id="tour-1",
        message="q?",
        rag_agent=rag_agent,
    ):
        events.append(event)

    types = _collect_event_types(events)
    assert types == ["chunk", "done"]


@pytest.mark.asyncio
async def test_stream_emits_error_and_NOT_done_when_rag_fails(
    monkeypatch, fake_tour_session, fake_session_maker
):
    async def fake_get_session(db, sid):
        return fake_tour_session
    monkeypatch.setattr(
        "app.application.tour_chat_service.get_session", fake_get_session
    )
    async def fake_record_events(*args, **kwargs):
        return None
    monkeypatch.setattr(
        "app.application.tour_chat_service.record_events", fake_record_events
    )

    rag_agent = MagicMock()
    rag_agent.run = AsyncMock(side_effect=RuntimeError("boom"))

    events = []
    async for event in ask_stream_tour(
        db_session=MagicMock(),
        session_maker=fake_session_maker,
        tour_session_id="tour-1",
        message="q?",
        rag_agent=rag_agent,
    ):
        events.append(event)

    types = _collect_event_types(events)
    assert "error" in types, f"expected error event, got {types}"
    assert "done" not in types, (
        f"PERFOPS-P1-02 regression: 'done' must not follow 'error', got {types}"
    )
