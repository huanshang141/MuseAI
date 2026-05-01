"""Merged TTS core tests: provider, service, settings, and API."""

import base64
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.tts_service import TTSService
from app.config.settings import Settings
from app.domain.entities import Prompt
from app.domain.value_objects import PromptId
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig
from app.infra.providers.tts.factory import create_tts_provider
from app.infra.providers.tts.mock import MockTTSProvider
from app.infra.providers.tts.xiaomi import XiaomiTTSProvider
from app.main import app


# ---------------------------------------------------------------------------
# Helpers (deduplicated)
# ---------------------------------------------------------------------------

def _make_prompt(
    key: str,
    content: str,
    voice: str | None = None,
    voice_description: str | None = None,
) -> Prompt:
    variables = []
    if voice:
        variables.append({"name": "__voice__", "description": voice})
    if voice_description:
        variables.append({"name": "__voice_description__", "description": voice_description})
    return Prompt(
        id=PromptId(value=f"prompt-{key}"),
        key=key,
        name=f"Test {key}",
        description=None,
        category="tts",
        content=content,
        variables=variables,
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


async def _async_iter(items):
    for item in items:
        yield item


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


# ---------------------------------------------------------------------------
# Provider tests (from test_tts_provider.py)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Service tests (from test_tts_service.py)
# ---------------------------------------------------------------------------

class TestTTSService:
    def _make_service(self, prompt_gateway=None):
        provider = MockTTSProvider()
        if prompt_gateway is None:
            prompt_gateway = AsyncMock()
            prompt_gateway.get_entity = AsyncMock(return_value=None)
        return TTSService(provider=provider, prompt_gateway=prompt_gateway)

    def test_get_qa_tts_config_default_voice(self):
        service = self._make_service()
        config = service.get_qa_tts_config()
        assert config.voice == "冰糖"
        assert config.style == "用清晰专业的语气讲解，语速适中"

    def test_get_qa_tts_config_user_voice(self):
        service = self._make_service()
        config = service.get_qa_tts_config(user_voice="苏打")
        assert config.voice == "苏打"
        assert config.style == "用清晰专业的语气讲解，语速适中"

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_with_persona_voice(self):
        gateway = AsyncMock()
        prompt = _make_prompt("tour_tts_persona_a", "用沉稳专业的语气讲解", voice="白桦")
        gateway.get_entity = AsyncMock(return_value=prompt)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("A")
        assert config.voice == "白桦"
        assert config.style == "用沉稳专业的语气讲解"
        gateway.get_entity.assert_called_once_with("tour_tts_persona_a")

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_fallback_to_default_voice(self):
        gateway = AsyncMock()
        prompt = _make_prompt("tour_tts_persona_a", "用沉稳专业的语气讲解")
        gateway.get_entity = AsyncMock(return_value=prompt)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("A")
        assert config.voice == "冰糖"
        assert config.style == "用沉稳专业的语气讲解"

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_fallback_when_no_prompt(self):
        gateway = AsyncMock()
        gateway.get_entity = AsyncMock(return_value=None)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("B")
        assert config.voice == "冰糖"
        assert config.style == "用温和亲切的语气讲解，语速适中"

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_all_personas(self):
        for persona, voice in [("A", "白桦"), ("B", "苏打"), ("C", "茉莉")]:
            gateway = AsyncMock()
            prompt = _make_prompt(
                f"tour_tts_persona_{persona.lower()}",
                f"Style for {persona}",
                voice=voice,
            )
            gateway.get_entity = AsyncMock(return_value=prompt)
            service = self._make_service(prompt_gateway=gateway)

            config = await service.get_tour_tts_config(persona)
            assert config.voice == voice
            assert config.style == f"Style for {persona}"


# ---------------------------------------------------------------------------
# Settings tests (from test_tts_settings.py)
# ---------------------------------------------------------------------------

class TestTTSSettings:
    def test_default_values(self):
        settings = Settings(
            JWT_SECRET="test-secret-that-is-long-enough-32chars",
            LLM_API_KEY="test-key",
            APP_ENV="development",
            TTS_API_KEY="",
            _env_file=None,
        )
        assert settings.TTS_ENABLED is True
        assert settings.TTS_PROVIDER == "xiaomi"
        assert settings.TTS_BASE_URL == "https://api.xiaomimimo.com/v1"
        assert settings.TTS_API_KEY == ""
        assert settings.TTS_MODEL == "mimo-v2.5-tts"
        assert settings.TTS_DEFAULT_VOICE == "冰糖"
        assert settings.TTS_TIMEOUT == 30.0
        assert settings.TTS_VOICE_DESIGN_MODEL == "mimo-v2.5-tts-voicedesign"

    def test_production_requires_tts_api_key_when_provider_set(self):
        try:
            Settings(
                JWT_SECRET="test-secret-that-is-long-enough-32chars",
                LLM_API_KEY="test-key",
                APP_ENV="production",
                TTS_PROVIDER="xiaomi",
                TTS_API_KEY="",
                CORS_ORIGINS="https://example.com",
            )
            assert False, "Should have raised"
        except ValueError as e:
            assert "TTS_API_KEY" in str(e)

    def test_production_allows_empty_tts_key_when_disabled(self):
        settings = Settings(
            JWT_SECRET="test-secret-that-is-long-enough-32chars",
            LLM_API_KEY="test-key",
            APP_ENV="production",
            TTS_ENABLED=False,
            TTS_PROVIDER="xiaomi",
            TTS_API_KEY="",
            CORS_ORIGINS="https://example.com",
        )
        assert settings.TTS_ENABLED is False

    def test_production_allows_empty_tts_key_when_mock(self):
        settings = Settings(
            JWT_SECRET="test-secret-that-is-long-enough-32chars",
            LLM_API_KEY="test-key",
            APP_ENV="production",
            TTS_PROVIDER="mock",
            TTS_API_KEY="",
            CORS_ORIGINS="https://example.com",
        )
        assert settings.TTS_PROVIDER == "mock"


# ---------------------------------------------------------------------------
# API tests (from test_tts_api.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_tts_service():
    service = AsyncMock()
    service.provider = AsyncMock()
    service.provider.synthesize_stream = MagicMock(
        return_value=_async_iter(["AAAA", "BBBB"])
    )
    return service


@pytest.mark.asyncio
async def test_synthesize_endpoint(mock_tts_service):
    with patch("app.api.tts._get_tts_service", return_value=mock_tts_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": "你好", "voice": "冰糖"},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "audio" in data
    assert data["format"] == "pcm16"
    assert data["audio"] == "AAAABBBB"


@pytest.mark.asyncio
async def test_synthesize_returns_503_when_tts_unavailable():
    with patch("app.api.tts._get_tts_service", return_value=None):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": "你好", "voice": "冰糖"},
            )
    assert resp.status_code == 503
