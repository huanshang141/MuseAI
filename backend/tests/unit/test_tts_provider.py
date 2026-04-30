from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig
from app.infra.providers.tts.factory import create_tts_provider
from app.infra.providers.tts.mock import MockTTSProvider
from app.infra.providers.tts.xiaomi import XiaomiTTSProvider
from app.config.settings import Settings


class TestTTSConfig:
    def test_voice_only(self):
        config = TTSConfig(voice="冰糖")
        assert config.voice == "冰糖"
        assert config.style is None

    def test_voice_with_style(self):
        config = TTSConfig(voice="茉莉", style="用温柔的语气")
        assert config.voice == "茉莉"
        assert config.style == "用温柔的语气"


class TestBaseTTSProvider:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseTTSProvider()


class TestMockTTSProvider:
    @pytest.mark.asyncio
    async def test_synthesize_stream_yields_empty_chunk(self):
        provider = MockTTSProvider()
        config = TTSConfig(voice="冰糖")
        chunks = []
        async for chunk in provider.synthesize_stream("hello", config):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert chunks[0] == ""

    @pytest.mark.asyncio
    async def test_synthesize_returns_empty_bytes(self):
        provider = MockTTSProvider()
        config = TTSConfig(voice="冰糖")
        result = await provider.synthesize("hello", config)
        assert result == b""

    @pytest.mark.asyncio
    async def test_close(self):
        provider = MockTTSProvider()
        await provider.close()  # should not raise


class _MockAsyncIterator:
    """Helper to create a proper async iterator from a list of items."""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration from None


class TestXiaomiTTSProvider:
    def _make_provider(self):
        return XiaomiTTSProvider(
            base_url="https://api.xiaomimimo.com/v1",
            api_key="test-key",
            model="mimo-v2.5-tts",
            timeout=30.0,
        )

    @pytest.mark.asyncio
    async def test_synthesize_stream_builds_correct_messages(self):
        provider = self._make_provider()
        config = TTSConfig(voice="冰糖", style="用温柔的语气")

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock()
        mock_chunk.choices[0].delta.audio = {"data": "dGVzdA=="}  # base64 "test"

        mock_stream = _MockAsyncIterator([mock_chunk])

        with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_stream):
            chunks = []
            async for chunk in provider.synthesize_stream("你好", config):
                chunks.append(chunk)

        assert chunks == ["dGVzdA=="]

    @pytest.mark.asyncio
    async def test_synthesize_stream_no_style(self):
        provider = self._make_provider()
        config = TTSConfig(voice="苏打")

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock()
        mock_chunk.choices[0].delta.audio = {"data": "YQ=="}

        mock_stream = _MockAsyncIterator([mock_chunk])

        create_mock = patch.object(
            provider.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_stream,
        )
        with create_mock as mock_create:
            chunks = []
            async for chunk in provider.synthesize_stream("你好", config):
                chunks.append(chunk)

        # Verify no user message when style is None
        call_args = mock_create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == "你好"

    @pytest.mark.asyncio
    async def test_synthesize_stream_skips_empty_audio(self):
        provider = self._make_provider()
        config = TTSConfig(voice="冰糖")

        mock_chunk_no_audio = MagicMock()
        mock_chunk_no_audio.choices = [MagicMock()]
        mock_chunk_no_audio.choices[0].delta = MagicMock()
        mock_chunk_no_audio.choices[0].delta.audio = None

        mock_chunk_with_audio = MagicMock()
        mock_chunk_with_audio.choices = [MagicMock()]
        mock_chunk_with_audio.choices[0].delta = MagicMock()
        mock_chunk_with_audio.choices[0].delta.audio = {"data": "YQ=="}

        mock_stream = _MockAsyncIterator([mock_chunk_no_audio, mock_chunk_with_audio])

        with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_stream):
            chunks = []
            async for chunk in provider.synthesize_stream("你好", config):
                chunks.append(chunk)

        assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_close(self):
        provider = self._make_provider()
        with patch.object(provider.client, "close", new_callable=AsyncMock) as mock_close:
            await provider.close()
            mock_close.assert_called_once()


class TestCreateTTSProvider:
    def _make_settings(self, **overrides):
        defaults = {
            "TTS_ENABLED": True,
            "TTS_PROVIDER": "xiaomi",
            "TTS_BASE_URL": "https://api.xiaomimimo.com/v1",
            "TTS_API_KEY": "test-key",
            "TTS_MODEL": "mimo-v2.5-tts",
            "TTS_DEFAULT_VOICE": "冰糖",
            "TTS_TIMEOUT": 30.0,
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def test_returns_xiaomi_provider(self):
        settings = self._make_settings()
        provider = create_tts_provider(settings)
        assert isinstance(provider, XiaomiTTSProvider)

    def test_returns_mock_provider(self):
        settings = self._make_settings(TTS_PROVIDER="mock")
        provider = create_tts_provider(settings)
        assert isinstance(provider, MockTTSProvider)

    def test_returns_none_when_disabled(self):
        settings = self._make_settings(TTS_ENABLED=False)
        provider = create_tts_provider(settings)
        assert provider is None

    def test_returns_none_when_no_api_key(self):
        settings = self._make_settings(TTS_API_KEY="")
        provider = create_tts_provider(settings)
        assert provider is None

    def test_returns_none_for_unknown_provider(self):
        settings = self._make_settings(TTS_PROVIDER="unknown")
        provider = create_tts_provider(settings)
        assert provider is None

    def test_mock_does_not_require_api_key(self):
        settings = self._make_settings(TTS_PROVIDER="mock", TTS_API_KEY="")
        provider = create_tts_provider(settings)
        assert isinstance(provider, MockTTSProvider)
