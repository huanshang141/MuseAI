import json
import pytest
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.tour import TourChatRequest
from app.infra.providers.tts.base import TTSConfig


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


class TestTourChatRequestTTSField:
    def test_default_tts_disabled(self):
        req = TourChatRequest(message="hi")
        assert req.tts is False

    def test_tts_enabled(self):
        req = TourChatRequest(message="hi", tts=True)
        assert req.tts is True


class TestTourStreamTTSEvents:
    """Verify TTS audio events are interleaved with text events in tour stream."""

    @pytest.mark.asyncio
    async def test_tts_events_before_done(self):
        """ask_stream_tour should yield audio_start/chunk/end before done when TTS is enabled."""
        from app.application.tour_chat_service import ask_stream_tour

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
        from app.application.tour_chat_service import ask_stream_tour

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
        from app.application.tour_chat_service import ask_stream_tour

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
