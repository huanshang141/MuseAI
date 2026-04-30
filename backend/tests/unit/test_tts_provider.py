import pytest
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig
from app.infra.providers.tts.mock import MockTTSProvider


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
