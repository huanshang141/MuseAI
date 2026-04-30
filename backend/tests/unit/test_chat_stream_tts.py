import json
import pytest
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.sse_events import (
    sse_chat_audio_start,
    sse_chat_audio_chunk,
    sse_chat_audio_end,
)
from app.infra.providers.tts.base import TTSConfig
from app.infra.providers.tts.mock import MockTTSProvider


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


class TestAskRequestTTSFields:
    def test_default_tts_disabled(self):
        from app.api.chat import AskRequest
        req = AskRequest(session_id="s1", message="hi")
        assert req.tts is False
        assert req.tts_voice is None

    def test_tts_enabled(self):
        from app.api.chat import AskRequest
        req = AskRequest(session_id="s1", message="hi", tts=True, tts_voice="冰糖")
        assert req.tts is True
        assert req.tts_voice == "冰糖"


class TestChatStreamTTSEvents:
    """Verify TTS audio events are interleaved with text events."""

    @pytest.mark.asyncio
    async def test_simple_stream_appends_tts_events(self):
        """ask_question_stream should yield audio_start/chunk/end before done."""
        from app.application.chat_stream_service import ask_question_stream

        mock_llm = AsyncMock()
        mock_llm.generate_stream = MagicMock(return_value=_async_iter(["你好"]))

        tts_provider = MockTTSProvider()
        tts_config = TTSConfig(voice="冰糖", style="用清晰专业的语气讲解，语速适中")

        session = AsyncMock()

        with patch("app.application.chat_stream_service.add_message"):
            events = []
            async for event in ask_question_stream(
                session=session,
                session_id="s1",
                message="hi",
                llm_provider=mock_llm,
                user_id="u1",
                tts_provider=tts_provider,
                tts_config=tts_config,
            ):
                events.append(json.loads(event.removeprefix("data: ").removesuffix("\n\n")))

        types = [e["type"] for e in events]
        assert "audio_start" in types
        assert "audio_chunk" in types
        assert "audio_end" in types
        # Audio events should come before done (sentence-level streaming)
        done_idx = types.index("done")
        audio_start_idx = types.index("audio_start")
        assert audio_start_idx < done_idx

    @pytest.mark.asyncio
    async def test_no_tts_events_when_provider_none(self):
        """When tts_provider is None, no audio events should be emitted."""
        from app.application.chat_stream_service import ask_question_stream

        mock_llm = AsyncMock()
        mock_llm.generate_stream = MagicMock(return_value=_async_iter(["你好"]))

        session = AsyncMock()

        with patch("app.application.chat_stream_service.add_message"):
            events = []
            async for event in ask_question_stream(
                session=session,
                session_id="s1",
                message="hi",
                llm_provider=mock_llm,
                user_id="u1",
                tts_provider=None,
                tts_config=None,
            ):
                events.append(json.loads(event.removeprefix("data: ").removesuffix("\n\n")))

        types = [e["type"] for e in events]
        assert "audio_start" not in types
        assert "audio_chunk" not in types
