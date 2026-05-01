"""Merged tour chat tests.

Combines tests from:
- test_tour_chat_service.py  (build_system_prompt unit tests)
- test_tour_chat_stream.py   (ask_stream_tour stream-behavior tests)
- test_tour_stream_tts.py    (TTS audio event interleaving tests)
"""

import json
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.tour import TourChatRequest
from app.application.tour_chat_service import (
    ASSUMPTION_CONTEXTS,
    HALL_DESCRIPTIONS,
    PERSONA_PROMPTS,
    ask_stream_tour,
    build_system_prompt,
)
from app.infra.providers.tts.base import TTSConfig


# ---------------------------------------------------------------------------
# Helpers: Tour Chat Stream
# ---------------------------------------------------------------------------

def _collect_event_types(events: list[str]) -> list[str]:
    parsed = []
    for raw in events:
        assert raw.startswith("data: ")
        assert raw.endswith("\n\n")
        payload = json.loads(raw[len("data: "):-2])
        parsed.append(payload.get("event"))
    return parsed


# ---------------------------------------------------------------------------
# Helpers: Tour Stream TTS
# ---------------------------------------------------------------------------

def _parse_events(raw: str) -> list[dict]:
    """Parse SSE stream into list of JSON payloads."""
    events = []
    for line in raw.strip().split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


async def _async_iter(items):
    """Helper to create an async iterator from a list."""
    for item in items:
        yield item


def _make_mock_tour_session():
    """Create a mock tour session with required attributes."""
    session = AsyncMock()
    session.persona = "A"
    session.assumption = "A"
    session.current_hall = "relic-hall"
    session.visited_exhibit_ids = []
    return session


# ---------------------------------------------------------------------------
# Fixtures: Tour Chat Stream
# ---------------------------------------------------------------------------

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


@pytest.fixture
def fake_llm_provider():
    provider = MagicMock()

    async def fake_stream(messages):
        for token in ["hello", " ", "world"]:
            yield token

    provider.generate_stream = fake_stream
    return provider


# ===================================================================
# Tour Chat Service Tests (build_system_prompt)
# ===================================================================

def test_build_system_prompt_persona_a():
    prompt = build_system_prompt(persona="A", assumption="A")
    assert PERSONA_PROMPTS["A"] in prompt
    assert ASSUMPTION_CONTEXTS["A"] in prompt


def test_build_system_prompt_persona_b():
    prompt = build_system_prompt(persona="B", assumption="B")
    assert PERSONA_PROMPTS["B"] in prompt
    assert ASSUMPTION_CONTEXTS["B"] in prompt


def test_build_system_prompt_persona_c():
    prompt = build_system_prompt(persona="C", assumption="C")
    assert PERSONA_PROMPTS["C"] in prompt
    assert ASSUMPTION_CONTEXTS["C"] in prompt


def test_build_system_prompt_with_hall():
    prompt = build_system_prompt(persona="A", assumption="A", hall="relic-hall")
    assert HALL_DESCRIPTIONS["relic-hall"] in prompt


def test_build_system_prompt_with_unknown_hall():
    prompt = build_system_prompt(persona="A", assumption="A", hall="unknown-hall")
    assert "当前展厅" not in prompt


def test_build_system_prompt_with_exhibit_context():
    prompt = build_system_prompt(
        persona="A", assumption="A", exhibit_context="人面鱼纹盆，红陶制品"
    )
    assert "人面鱼纹盆，红陶制品" in prompt
    assert "当前展品信息" in prompt


def test_build_system_prompt_with_visited_exhibits():
    prompt = build_system_prompt(
        persona="A", assumption="A", visited_exhibits=["exhibit-1", "exhibit-2"]
    )
    assert "exhibit-1" in prompt
    assert "exhibit-2" in prompt
    assert "避免重复介绍" in prompt


def test_build_system_prompt_all_parts():
    prompt = build_system_prompt(
        persona="B",
        assumption="C",
        hall="site-hall",
        exhibit_context="半地穴式房屋",
        visited_exhibits=["exhibit-1"],
    )
    assert PERSONA_PROMPTS["B"] in prompt
    assert ASSUMPTION_CONTEXTS["C"] in prompt
    assert HALL_DESCRIPTIONS["site-hall"] in prompt
    assert "半地穴式房屋" in prompt
    assert "exhibit-1" in prompt


def test_build_system_prompt_default_persona():
    prompt = build_system_prompt(persona="X", assumption="A")
    assert PERSONA_PROMPTS["A"] in prompt


def test_persona_prompts_have_all_keys():
    assert set(PERSONA_PROMPTS.keys()) == {"A", "B", "C"}


def test_assumption_contexts_have_all_keys():
    assert set(ASSUMPTION_CONTEXTS.keys()) == {"A", "B", "C"}


def test_hall_descriptions_have_expected_slugs():
    assert "relic-hall" in HALL_DESCRIPTIONS
    assert "site-hall" in HALL_DESCRIPTIONS


# ===================================================================
# Tour Chat Stream Tests (ask_stream_tour behaviour)
# ===================================================================

@pytest.mark.asyncio
async def test_stream_emits_chunk_then_done_on_success(
    monkeypatch, fake_tour_session, fake_session_maker, fake_llm_provider
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
    rag_agent.run = AsyncMock(return_value={"answer": "hello", "documents": []})
    rag_agent.prompt_gateway = None

    events = []
    async for event in ask_stream_tour(
        db_session=MagicMock(),
        session_maker=fake_session_maker,
        tour_session_id="tour-1",
        message="q?",
        rag_agent=rag_agent,
        llm_provider=fake_llm_provider,
    ):
        events.append(event)

    types = _collect_event_types(events)
    assert types == ["chunk", "chunk", "chunk", "done"]


@pytest.mark.asyncio
async def test_stream_emits_error_and_NOT_done_when_rag_fails(
    monkeypatch, fake_tour_session, fake_session_maker, fake_llm_provider
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
        llm_provider=fake_llm_provider,
    ):
        events.append(event)

    types = _collect_event_types(events)
    assert "error" in types, f"expected error event, got {types}"
    assert "done" not in types, (
        f"PERFOPS-P1-02 regression: 'done' must not follow 'error', got {types}"
    )


@pytest.mark.asyncio
async def test_stream_logs_error_when_event_persistence_fails(
    monkeypatch, fake_tour_session, fake_session_maker, fake_llm_provider
):
    async def fake_get_session(db, sid):
        return fake_tour_session

    monkeypatch.setattr(
        "app.application.tour_chat_service.get_session", fake_get_session
    )

    async def failing_record_events(*args, **kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(
        "app.application.tour_chat_service.record_events", failing_record_events
    )

    mock_bound_logger = MagicMock()
    mock_logger = MagicMock()
    mock_logger.bind.return_value = mock_bound_logger
    monkeypatch.setattr("app.application.tour_chat_service.logger", mock_logger)

    rag_agent = MagicMock()
    rag_agent.run = AsyncMock(return_value={"answer": "hello", "documents": []})
    rag_agent.prompt_gateway = None

    events = []
    async for event in ask_stream_tour(
        db_session=MagicMock(),
        session_maker=fake_session_maker,
        tour_session_id="tour-1",
        message="q?",
        rag_agent=rag_agent,
        llm_provider=fake_llm_provider,
    ):
        events.append(event)

    types = _collect_event_types(events)
    assert types == ["chunk", "chunk", "chunk", "done"]
    mock_bound_logger.error.assert_called_once()


# ===================================================================
# Tour Chat Request TTS Field Tests
# ===================================================================

class TestTourChatRequestTTSField:
    def test_default_tts_disabled(self):
        req = TourChatRequest(message="hi")
        assert req.tts is False

    def test_tts_enabled(self):
        req = TourChatRequest(message="hi", tts=True)
        assert req.tts is True


# ===================================================================
# Tour Stream TTS Event Tests
# ===================================================================

class TestTourStreamTTSEvents:
    """Verify TTS audio events are interleaved with text events in tour stream."""

    @pytest.mark.asyncio
    async def test_tts_events_before_done(self):
        """ask_stream_tour should yield audio_start/chunk/end before done when TTS is enabled."""
        mock_llm = AsyncMock()
        mock_llm.generate_stream = MagicMock(return_value=_async_iter(["你好"]))

        mock_rag = AsyncMock()
        mock_rag.run = AsyncMock(return_value={
            "filtered_documents": [],
            "reranked_documents": [],
            "documents": [],
        })
        mock_rag.prompt_gateway = None

        mock_tts_provider = AsyncMock()
        mock_tts_provider.synthesize_stream = MagicMock(
            return_value=_async_iter(["base64audio1", "base64audio2"])
        )

        mock_tts_service = AsyncMock()
        mock_tts_service.get_tour_tts_config = AsyncMock(
            return_value=TTSConfig(voice="冰糖", style="用温和亲切的语气讲解")
        )

        db_session = AsyncMock()
        session_maker = AsyncMock()
        session_maker.__aenter__ = AsyncMock(return_value=AsyncMock())
        session_maker.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.application.tour_chat_service.get_session", return_value=_make_mock_tour_session()),
            patch("app.application.tour_chat_service.record_events", new_callable=AsyncMock),
        ):
            events = []
            async for event in ask_stream_tour(
                db_session=db_session,
                session_maker=session_maker,
                tour_session_id="ts1",
                message="hi",
                rag_agent=mock_rag,
                llm_provider=mock_llm,
                tts_provider=mock_tts_provider,
                tts_service=mock_tts_service,
                persona="A",
            ):
                events.append(json.loads(event.removeprefix("data: ").removesuffix("\n\n")))

        event_names = [e.get("event") for e in events]
        assert "audio_start" in event_names
        assert "audio_chunk" in event_names
        assert "audio_end" in event_names
        # Audio events should come before done (sentence-level streaming)
        done_idx = event_names.index("done")
        audio_start_idx = event_names.index("audio_start")
        assert audio_start_idx < done_idx

    @pytest.mark.asyncio
    async def test_no_tts_events_when_provider_none(self):
        """When tts_provider is None, no audio events should be emitted."""
        mock_llm = AsyncMock()
        mock_llm.generate_stream = MagicMock(return_value=_async_iter(["你好"]))

        mock_rag = AsyncMock()
        mock_rag.run = AsyncMock(return_value={
            "filtered_documents": [],
            "reranked_documents": [],
            "documents": [],
        })
        mock_rag.prompt_gateway = None

        db_session = AsyncMock()
        session_maker = AsyncMock()
        session_maker.__aenter__ = AsyncMock(return_value=AsyncMock())
        session_maker.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.application.tour_chat_service.get_session", return_value=_make_mock_tour_session()),
            patch("app.application.tour_chat_service.record_events", new_callable=AsyncMock),
        ):
            events = []
            async for event in ask_stream_tour(
                db_session=db_session,
                session_maker=session_maker,
                tour_session_id="ts1",
                message="hi",
                rag_agent=mock_rag,
                llm_provider=mock_llm,
                tts_provider=None,
                tts_service=None,
                persona=None,
            ):
                events.append(json.loads(event.removeprefix("data: ").removesuffix("\n\n")))

        event_names = [e.get("event") for e in events]
        assert "audio_start" not in event_names
        assert "audio_chunk" not in event_names
        assert "audio_end" not in event_names

    @pytest.mark.asyncio
    async def test_tts_error_yields_audio_error(self):
        """When TTS synthesis fails, an audio_error event should be emitted."""
        mock_llm = AsyncMock()
        mock_llm.generate_stream = MagicMock(return_value=_async_iter(["你好"]))

        mock_rag = AsyncMock()
        mock_rag.run = AsyncMock(return_value={
            "filtered_documents": [],
            "reranked_documents": [],
            "documents": [],
        })
        mock_rag.prompt_gateway = None

        mock_tts_provider = AsyncMock()
        mock_tts_provider.synthesize_stream = MagicMock(side_effect=RuntimeError("TTS service down"))

        mock_tts_service = AsyncMock()
        mock_tts_service.get_tour_tts_config = AsyncMock(
            return_value=TTSConfig(voice="冰糖", style="用温和亲切的语气讲解")
        )

        db_session = AsyncMock()
        session_maker = AsyncMock()
        session_maker.__aenter__ = AsyncMock(return_value=AsyncMock())
        session_maker.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.application.tour_chat_service.get_session", return_value=_make_mock_tour_session()),
            patch("app.application.tour_chat_service.record_events", new_callable=AsyncMock),
        ):
            events = []
            async for event in ask_stream_tour(
                db_session=db_session,
                session_maker=session_maker,
                tour_session_id="ts1",
                message="hi",
                rag_agent=mock_rag,
                llm_provider=mock_llm,
                tts_provider=mock_tts_provider,
                tts_service=mock_tts_service,
                persona="B",
            ):
                events.append(json.loads(event.removeprefix("data: ").removesuffix("\n\n")))

        event_names = [e.get("event") for e in events]
        assert "audio_start" in event_names
        assert "audio_error" in event_names
        # Audio events should come before done (sentence-level streaming)
        done_idx = event_names.index("done")
        audio_start_idx = event_names.index("audio_start")
        assert audio_start_idx < done_idx
        audio_error = next(e for e in events if e.get("event") == "audio_error")
        assert audio_error["code"] == "TTS_ERROR"
