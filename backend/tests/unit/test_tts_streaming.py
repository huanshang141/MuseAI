import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.application.tts_streaming import TTSStreamManager, extract_sentences
from app.infra.providers.tts.base import TTSConfig
from app.infra.providers.tts.mock import MockTTSProvider


async def _async_iter(items):
    for item in items:
        yield item


class TestExtractSentences:
    def test_chinese_period(self):
        sentences, remainder = extract_sentences("你好。世界。")
        assert len(sentences) == 2
        assert sentences[0] == "你好。"
        assert sentences[1] == "世界。"
        assert remainder == ""

    def test_chinese_exclamation(self):
        sentences, remainder = extract_sentences("太好了！谢谢。")
        assert len(sentences) == 2
        assert sentences[0] == "太好了！"
        assert sentences[1] == "谢谢。"

    def test_english_period(self):
        sentences, remainder = extract_sentences("Hello world. How are you?")
        assert len(sentences) == 2
        assert sentences[0] == "Hello world."
        assert sentences[1] == "How are you?"

    def test_no_complete_sentence(self):
        sentences, remainder = extract_sentences("你好世界")
        assert len(sentences) == 0
        assert remainder == "你好世界"

    def test_double_newline(self):
        sentences, remainder = extract_sentences("第一段。\n\n第二段。")
        assert len(sentences) == 2
        assert sentences[0] == "第一段。"
        assert sentences[1] == "第二段。"

    def test_mixed_content(self):
        sentences, remainder = extract_sentences("你好。世界！")
        assert len(sentences) == 2
        assert sentences[0] == "你好。"
        assert sentences[1] == "世界！"

    def test_remainder_with_partial(self):
        sentences, remainder = extract_sentences("你好。世界")
        assert len(sentences) == 1
        assert sentences[0] == "你好。"
        assert remainder == "世界"

    def test_empty_string(self):
        sentences, remainder = extract_sentences("")
        assert len(sentences) == 0
        assert remainder == ""

    def test_whitespace_handling(self):
        sentences, remainder = extract_sentences("  你好 。 世界 。 ")
        assert len(sentences) == 2
        assert sentences[0] == "你好 。"
        assert sentences[1] == "世界 。"


class TestTTSStreamManager:
    @pytest.mark.asyncio
    async def test_disabled_when_no_provider(self):
        mgr = TTSStreamManager(None, None, schema="chat")
        assert not mgr.enabled
        events = [e async for e in mgr.feed("你好")]
        assert events == []
        events = [e async for e in mgr.flush()]
        assert events == []

    @pytest.mark.asyncio
    async def test_yields_audio_for_complete_sentence(self):
        tts_provider = MockTTSProvider()
        tts_config = TTSConfig(voice="冰糖", style="test")
        mgr = TTSStreamManager(tts_provider, tts_config, schema="chat")

        # Feed a complete sentence, then flush to wait for background task
        feed_events = [e async for e in mgr.feed("你好。")]
        flush_events = [e async for e in mgr.flush()]
        events = feed_events + flush_events
        assert len(events) >= 2  # audio_start + audio_end
        first_event = json.loads(events[0].removeprefix("data: ").removesuffix("\n\n"))
        assert first_event["type"] == "audio_start"

    @pytest.mark.asyncio
    async def test_flushes_remainder(self):
        tts_provider = MockTTSProvider()
        tts_config = TTSConfig(voice="冰糖", style="test")
        mgr = TTSStreamManager(tts_provider, tts_config, schema="chat")

        # Feed incomplete sentence
        events = [e async for e in mgr.feed("你好")]
        assert events == []  # No complete sentence yet

        # Flush should send the remainder
        events = [e async for e in mgr.flush()]
        assert len(events) >= 2
        first_event = json.loads(events[0].removeprefix("data: ").removesuffix("\n\n"))
        assert first_event["type"] == "audio_start"

    @pytest.mark.asyncio
    async def test_tour_schema(self):
        tts_provider = MockTTSProvider()
        tts_config = TTSConfig(voice="冰糖", style="test")
        mgr = TTSStreamManager(tts_provider, tts_config, schema="tour")

        feed_events = [e async for e in mgr.feed("你好。")]
        flush_events = [e async for e in mgr.flush()]
        events = feed_events + flush_events
        assert len(events) >= 2
        first_event = json.loads(events[0].removeprefix("data: ").removesuffix("\n\n"))
        assert first_event["event"] == "audio_start"
