"""Merged TTS core tests: provider, service, settings, and API."""

import base64
import hashlib
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.deps import get_redis_cache
from app.application.tts_service import DEFAULT_TTS_STYLE, DEFAULT_TTS_VOICE, TTSService
from app.config.settings import Settings
from app.domain.entities import Prompt
from app.domain.value_objects import PromptId
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig, is_valid_wav
from app.infra.providers.tts.factory import create_tts_provider
from app.infra.providers.tts.mock import MockTTSProvider
from app.infra.providers.tts.xiaomi import XiaomiTTSProvider
from app.main import app
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from redis.exceptions import RedisError

# ---------------------------------------------------------------------------
# Helpers (deduplicated)
# ---------------------------------------------------------------------------


def _valid_wav(pcm: bytes = b"\x00\x00") -> bytes:
    fmt = (
        (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (24_000).to_bytes(4, "little")
        + (48_000).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
    )
    body = b"fmt " + len(fmt).to_bytes(4, "little") + fmt
    body += b"data" + len(pcm).to_bytes(4, "little") + pcm
    return b"RIFF" + (len(body) + 4).to_bytes(4, "little") + b"WAVE" + body


VALID_WAV = _valid_wav()


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
        config = TTSConfig(voice=DEFAULT_TTS_VOICE, style="用明亮自然的语气")
        assert config.voice == DEFAULT_TTS_VOICE
        assert config.style == "用明亮自然的语气"


class TestBaseTTSProvider:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseTTSProvider()


class TestMockTTSProvider:
    @pytest.mark.asyncio
    async def test_synthesize_stream_yields_valid_pcm16_chunk(self):
        provider = MockTTSProvider()
        config = TTSConfig(voice="冰糖")
        chunks = []
        async for chunk in provider.synthesize_stream("hello", config):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert base64.b64decode(chunks[0], validate=True)

    @pytest.mark.asyncio
    async def test_synthesize_returns_valid_wav(self):
        provider = MockTTSProvider()
        config = TTSConfig(voice="冰糖")
        result = await provider.synthesize("hello", config)
        assert is_valid_wav(result)

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
        config = TTSConfig(voice=DEFAULT_TTS_VOICE)

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
        with pytest.raises(ValidationError, match="TTS_PROVIDER must be one of"):
            self._make_settings(TTS_PROVIDER="unknown")

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
        assert config.style == DEFAULT_TTS_STYLE

    def test_get_qa_tts_config_user_voice(self):
        service = self._make_service()
        config = service.get_qa_tts_config(user_voice=DEFAULT_TTS_VOICE)
        assert config.voice == DEFAULT_TTS_VOICE
        assert config.style == DEFAULT_TTS_STYLE

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_uses_default_voice_over_persona_voice(self):
        gateway = AsyncMock()
        prompt = _make_prompt("tour_tts_persona_a", "用明亮自然的语气讲解", voice=DEFAULT_TTS_VOICE)
        gateway.get_entity = AsyncMock(return_value=prompt)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("A")
        assert config.voice == "冰糖"
        assert config.style == DEFAULT_TTS_STYLE
        gateway.get_entity.assert_called_once_with("tour_tts_persona_a")

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_fallback_to_default_voice(self):
        gateway = AsyncMock()
        prompt = _make_prompt("tour_tts_persona_a", "用明亮自然的语气讲解")
        gateway.get_entity = AsyncMock(return_value=prompt)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("A")
        assert config.voice == "冰糖"
        assert config.style == DEFAULT_TTS_STYLE

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_fallback_when_no_prompt(self):
        gateway = AsyncMock()
        gateway.get_entity = AsyncMock(return_value=None)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("B")
        assert config.voice == "冰糖"
        assert config.style == DEFAULT_TTS_STYLE

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_all_personas(self):
        for persona, voice in [
            ("A", DEFAULT_TTS_VOICE),
            ("B", DEFAULT_TTS_VOICE),
            ("C", DEFAULT_TTS_VOICE),
            ("D", DEFAULT_TTS_VOICE),
        ]:
            gateway = AsyncMock()
            prompt = _make_prompt(
                f"tour_tts_persona_{persona.lower()}",
                f"Style for {persona}",
                voice=voice,
            )
            gateway.get_entity = AsyncMock(return_value=prompt)
            service = self._make_service(prompt_gateway=gateway)

            config = await service.get_tour_tts_config(persona)
            assert config.voice == "冰糖"
            assert config.style == DEFAULT_TTS_STYLE


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
        with pytest.raises(ValueError, match="TTS_API_KEY"):
            Settings(
                JWT_SECRET="test-secret-that-is-long-enough-32chars",
                LLM_API_KEY="test-key",
                APP_ENV="production",
                TTS_PROVIDER="xiaomi",
                TTS_API_KEY="",
                CORS_ORIGINS="https://example.com",
            )

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
    service.provider.synthesize = AsyncMock(return_value=VALID_WAV)
    return service


@pytest.fixture
def tts_rate_redis():
    redis = AsyncMock()
    redis.check_rate_limit = AsyncMock(return_value=True)
    app.dependency_overrides[get_redis_cache] = lambda: redis
    yield redis
    app.dependency_overrides.pop(get_redis_cache, None)


@pytest.mark.asyncio
async def test_synthesize_endpoint(mock_tts_service, tts_rate_redis):
    with patch("app.api.tts._get_tts_service", return_value=mock_tts_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": " 你好 ", "voice": DEFAULT_TTS_VOICE},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "audio" in data
    assert data["format"] == "wav"
    assert base64.b64decode(data["audio"]) == VALID_WAV
    args, _ = mock_tts_service.provider.synthesize.call_args
    assert args[0] == "你好"
    assert args[1].voice == DEFAULT_TTS_VOICE
    rate_call = tts_rate_redis.check_rate_limit.await_args
    assert rate_call.args[0].startswith("tts_synthesize_ip:")
    assert not rate_call.args[0].startswith("guest:")
    assert rate_call.kwargs == {"max_requests": 300, "window_seconds": 60}


@pytest.mark.asyncio
async def test_synthesize_uses_hashed_session_and_shared_ip_limits(
    mock_tts_service,
    tts_rate_redis,
):
    session_token = "secret-session-token"
    with patch("app.api.tts._get_tts_service", return_value=mock_tts_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": "你好", "voice": DEFAULT_TTS_VOICE},
                headers={"X-Session-Token": session_token},
            )

    assert resp.status_code == 200
    token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
    calls = tts_rate_redis.check_rate_limit.await_args_list
    assert calls[0].args[0] == f"tts_synthesize_session:{token_hash}"
    assert session_token not in calls[0].args[0]
    assert calls[0].kwargs == {"max_requests": 30, "window_seconds": 60}
    assert calls[1].args[0].startswith("tts_synthesize_ip:")
    assert calls[1].kwargs == {"max_requests": 300, "window_seconds": 60}


@pytest.mark.asyncio
async def test_synthesize_returns_503_when_tts_unavailable(tts_rate_redis):
    with patch("app.api.tts._get_tts_service", return_value=None):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": "你好", "voice": "冰糖"},
            )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_synthesize_returns_502_for_invalid_wav(mock_tts_service, tts_rate_redis):
    mock_tts_service.provider.synthesize = AsyncMock(return_value=b"PCMDATA")
    with patch("app.api.tts._get_tts_service", return_value=mock_tts_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": "你好", "voice": DEFAULT_TTS_VOICE},
            )

    assert resp.status_code == 502
    assert resp.json()["detail"] == "TTS synthesis failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", "   ", "字" * 501])
async def test_synthesize_rejects_invalid_text_length(
    mock_tts_service,
    tts_rate_redis,
    text,
):
    with patch("app.api.tts._get_tts_service", return_value=mock_tts_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": text, "voice": DEFAULT_TTS_VOICE},
            )

    assert resp.status_code == 422
    mock_tts_service.provider.synthesize.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("voice", "声" * 65),
        ("style", "风" * 501),
        ("persona", "E"),
        ("persona", "a"),
    ],
)
async def test_synthesize_rejects_unbounded_or_unknown_config(
    mock_tts_service,
    tts_rate_redis,
    field,
    value,
):
    body = {"text": "你好", field: value}
    with patch("app.api.tts._get_tts_service", return_value=mock_tts_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/tts/synthesize", json=body)

    assert resp.status_code == 422
    mock_tts_service.provider.synthesize.assert_not_awaited()


@pytest.mark.asyncio
async def test_synthesize_keeps_empty_voice_compatibility(
    mock_tts_service,
    tts_rate_redis,
):
    with patch("app.api.tts._get_tts_service", return_value=mock_tts_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": "你好", "voice": ""},
            )

    assert resp.status_code == 200
    config = mock_tts_service.provider.synthesize.await_args.args[1]
    assert config.voice == DEFAULT_TTS_VOICE


@pytest.mark.asyncio
async def test_synthesize_returns_429_for_isolated_tts_limit(
    mock_tts_service,
    tts_rate_redis,
):
    tts_rate_redis.check_rate_limit.return_value = False
    with patch("app.api.tts._get_tts_service", return_value=mock_tts_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": "你好", "voice": DEFAULT_TTS_VOICE},
            )

    assert resp.status_code == 429
    assert tts_rate_redis.check_rate_limit.await_args.args[0].startswith(
        "tts_synthesize_ip:"
    )
    mock_tts_service.provider.synthesize.assert_not_awaited()


@pytest.mark.asyncio
async def test_synthesize_rate_limit_fails_closed_when_redis_unavailable(
    mock_tts_service,
    tts_rate_redis,
):
    tts_rate_redis.check_rate_limit.side_effect = RedisError("offline")
    with patch("app.api.tts._get_tts_service", return_value=mock_tts_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": "你好", "voice": DEFAULT_TTS_VOICE},
            )

    assert resp.status_code == 503
    mock_tts_service.provider.synthesize.assert_not_awaited()
