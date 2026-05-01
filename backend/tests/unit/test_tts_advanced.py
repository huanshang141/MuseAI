"""Merged TTS advanced tests: cached, streaming, persona API, and persona repository."""

import base64
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.api.admin.tts_persona import router
from app.api.deps import get_current_admin_user, get_db_session, get_prompt_cache
from app.application.tts_streaming import TTSStreamManager, extract_sentences
from app.domain.entities import Prompt
from app.domain.exceptions import PromptNotFoundError
from app.domain.value_objects import PromptId
from app.infra.postgres.adapters.prompt import PostgresPromptRepository
from app.infra.providers.tts.base import TTSConfig
from app.infra.providers.tts.cached import CachedTTSProvider
from app.infra.providers.tts.mock import MockTTSProvider


# ---------------------------------------------------------------------------
# Helpers (deduplicated)
# ---------------------------------------------------------------------------

async def _async_iter(items):
    for item in items:
        yield item


def _make_prompt(key="tour_tts_persona_a", voice_desc="五十多岁男性"):
    variables = []
    if voice_desc:
        variables.append({"name": "__voice_description__", "description": voice_desc})
    return Prompt(
        id=PromptId("prompt-1"),
        key=key,
        name="Tour TTS - Archaeologist",
        description=None,
        category="tts",
        content="用沉稳专业的语气讲解",
        variables=variables,
        is_active=True,
        current_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _create_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    mock_cache = MagicMock()
    mock_cache.refresh = MagicMock()

    async def override_session():
        yield AsyncMock()

    def override_admin():
        return {"id": "u1", "email": "admin@test.com", "role": "admin"}

    def override_cache():
        return mock_cache

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_current_admin_user] = override_admin
    app.dependency_overrides[get_prompt_cache] = override_cache

    return app, mock_cache


class FakeProvider:
    """A TTS provider that records calls and returns configurable chunks."""

    def __init__(self, chunks=None):
        self.call_count = 0
        self.last_text = None
        self.chunks = chunks or ["AAAA", "BBBB"]

    async def synthesize_stream(self, text, config):
        self.call_count += 1
        self.last_text = text
        for chunk in self.chunks:
            yield chunk

    async def synthesize(self, text, config):
        self.call_count += 1
        self.last_text = text
        return b"WAV_DATA"

    async def close(self):
        pass


def _mock_redis(get_return=None):
    """Create a mock Redis client with configurable get return value."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=get_return)
    redis.setex = AsyncMock()
    return redis


async def _collect(gen):
    return [chunk async for chunk in gen]


def _make_prompt_orm(prompt_id="p1", key="tour_tts_persona_a", variables=None):
    orm = MagicMock()
    orm.id = prompt_id
    orm.key = key
    orm.name = "Tour TTS - Archaeologist"
    orm.description = None
    orm.category = "tts"
    orm.content = "old content"
    orm.variables = variables or []
    orm.is_active = True
    orm.created_at = MagicMock(isoformat=MagicMock(return_value="2026-01-01T00:00:00"))
    orm.updated_at = MagicMock(isoformat=MagicMock(return_value="2026-01-01T00:00:00"))
    v = MagicMock()
    v.version = 1
    orm.versions = [v]
    return orm


# ---------------------------------------------------------------------------
# Streaming tests (from test_tts_streaming.py)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Cached tests (from test_tts_cached.py)
# ---------------------------------------------------------------------------

class TestCachedTTSProvider:
    @pytest.mark.asyncio
    async def test_cache_miss_calls_upstream_and_writes(self):
        inner = FakeProvider(chunks=["AA", "BB"])
        redis = _mock_redis(get_return=None)
        cached = CachedTTSProvider(inner, redis=redis)

        result = await _collect(cached.synthesize_stream("你好", TTSConfig(voice="冰糖")))

        assert result == ["AA", "BB"]
        assert inner.call_count == 1
        redis.get.assert_awaited_once()
        redis.setex.assert_awaited_once()
        # Verify the cached value is a JSON list of chunks
        args = redis.setex.call_args
        assert json.loads(args[0][2]) == ["AA", "BB"]

    @pytest.mark.asyncio
    async def test_cache_hit_skips_upstream(self):
        cached_chunks = ["CC", "DD"]
        redis = _mock_redis(get_return=json.dumps(cached_chunks).encode())
        inner = FakeProvider(chunks=["AA", "BB"])
        cached = CachedTTSProvider(inner, redis=redis)

        result = await _collect(cached.synthesize_stream("你好", TTSConfig(voice="冰糖")))

        assert result == ["CC", "DD"]
        assert inner.call_count == 0  # Upstream not called
        redis.setex.assert_not_awaited()  # No write needed

    @pytest.mark.asyncio
    async def test_different_text_uses_different_key(self):
        redis = _mock_redis(get_return=None)
        inner = FakeProvider(chunks=["AA"])
        cached = CachedTTSProvider(inner, redis=redis)

        await _collect(cached.synthesize_stream("你好", TTSConfig(voice="冰糖")))
        await _collect(cached.synthesize_stream("世界", TTSConfig(voice="冰糖")))

        assert inner.call_count == 2
        assert redis.get.await_count == 2
        # Verify different keys were used
        key1 = redis.get.call_args_list[0][0][0]
        key2 = redis.get.call_args_list[1][0][0]
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_different_voice_uses_different_key(self):
        redis = _mock_redis(get_return=None)
        inner = FakeProvider(chunks=["AA"])
        cached = CachedTTSProvider(inner, redis=redis)

        await _collect(cached.synthesize_stream("你好", TTSConfig(voice="冰糖")))
        await _collect(cached.synthesize_stream("你好", TTSConfig(voice="小溪")))

        assert inner.call_count == 2
        key1 = redis.get.call_args_list[0][0][0]
        key2 = redis.get.call_args_list[1][0][0]
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_different_style_uses_different_key(self):
        redis = _mock_redis(get_return=None)
        inner = FakeProvider(chunks=["AA"])
        cached = CachedTTSProvider(inner, redis=redis)

        await _collect(cached.synthesize_stream("你好", TTSConfig(voice="冰糖", style="A")))
        await _collect(cached.synthesize_stream("你好", TTSConfig(voice="冰糖", style="B")))

        assert inner.call_count == 2
        key1 = redis.get.call_args_list[0][0][0]
        key2 = redis.get.call_args_list[1][0][0]
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_redis_read_error_falls_through(self):
        redis = _mock_redis()
        redis.get = AsyncMock(side_effect=RedisError("connection lost"))
        inner = FakeProvider(chunks=["AA", "BB"])
        cached = CachedTTSProvider(inner, redis=redis)

        result = await _collect(cached.synthesize_stream("你好", TTSConfig(voice="冰糖")))

        assert result == ["AA", "BB"]
        assert inner.call_count == 1  # Falls through to upstream

    @pytest.mark.asyncio
    async def test_redis_write_error_still_returns_audio(self):
        redis = _mock_redis(get_return=None)
        redis.setex = AsyncMock(side_effect=RedisError("connection lost"))
        inner = FakeProvider(chunks=["AA", "BB"])
        cached = CachedTTSProvider(inner, redis=redis)

        result = await _collect(cached.synthesize_stream("你好", TTSConfig(voice="冰糖")))

        assert result == ["AA", "BB"]
        assert inner.call_count == 1  # Upstream still called

    @pytest.mark.asyncio
    async def test_synthesize_non_streaming_cache_miss(self):
        redis = _mock_redis(get_return=None)
        inner = FakeProvider()
        cached = CachedTTSProvider(inner, redis=redis)

        result = await cached.synthesize("你好", TTSConfig(voice="冰糖"))

        assert result == b"WAV_DATA"
        assert inner.call_count == 1
        redis.setex.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_synthesize_non_streaming_cache_hit(self):
        cached_wav = base64.b64encode(b"WAV_DATA").decode()
        redis = _mock_redis(get_return=cached_wav.encode())
        inner = FakeProvider()
        cached = CachedTTSProvider(inner, redis=redis)

        result = await cached.synthesize("你好", TTSConfig(voice="冰糖"))

        assert result == b"WAV_DATA"
        assert inner.call_count == 0

    @pytest.mark.asyncio
    async def test_ttl_is_passed_to_setex(self):
        redis = _mock_redis(get_return=None)
        inner = FakeProvider(chunks=["AA"])
        cached = CachedTTSProvider(inner, redis=redis, ttl=7200)

        await _collect(cached.synthesize_stream("你好", TTSConfig(voice="冰糖")))

        args = redis.setex.call_args[0]
        assert args[1] == 7200  # TTL

    @pytest.mark.asyncio
    async def test_close_delegates(self):
        inner = FakeProvider()
        inner.close = AsyncMock()
        redis = _mock_redis()
        cached = CachedTTSProvider(inner, redis=redis)

        await cached.close()
        inner.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# Persona API tests (from test_tts_persona_api.py)
# ---------------------------------------------------------------------------

class TestListTtsPersonas:
    def test_returns_personas(self):
        app, mock_cache = _create_app()
        prompts = [_make_prompt("tour_tts_persona_a"), _make_prompt("tour_tts_persona_b")]

        with patch("app.api.admin.tts_persona.PostgresPromptRepository") as MockRepo:
            MockRepo.return_value.list_all = AsyncMock(return_value=prompts)
            client = TestClient(app)
            response = client.get("/api/v1/admin/tts/personas")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["personas"][0]["voice_description"] == "五十多岁男性"


class TestGetTtsPersona:
    def test_get_by_letter(self):
        app, _ = _create_app()
        prompt = _make_prompt("tour_tts_persona_a")

        with patch("app.api.admin.tts_persona.PostgresPromptRepository") as MockRepo:
            MockRepo.return_value.get_by_key = AsyncMock(return_value=prompt)
            client = TestClient(app)
            response = client.get("/api/v1/admin/tts/personas/a")

        assert response.status_code == 200
        assert response.json()["key"] == "tour_tts_persona_a"

    def test_invalid_persona_returns_400(self):
        app, _ = _create_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/admin/tts/personas/x")
        assert response.status_code == 400

    def test_not_found_returns_404(self):
        app, _ = _create_app()

        with patch("app.api.admin.tts_persona.PostgresPromptRepository") as MockRepo:
            MockRepo.return_value.get_by_key = AsyncMock(return_value=None)
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/admin/tts/personas/a")

        assert response.status_code == 404


class TestUpdateTtsPersona:
    def test_update_content_and_voice_description(self):
        app, mock_cache = _create_app()
        existing = _make_prompt("tour_tts_persona_a", voice_desc="old voice")
        updated = _make_prompt("tour_tts_persona_a", voice_desc="new voice")
        updated.content = "new style"

        with patch("app.api.admin.tts_persona.PostgresPromptRepository") as MockRepo:
            MockRepo.return_value.get_by_key = AsyncMock(return_value=existing)
            MockRepo.return_value.update_with_variables = AsyncMock(return_value=updated)
            client = TestClient(app)
            response = client.put(
                "/api/v1/admin/tts/personas/a",
                json={
                    "content": "new style",
                    "voice_description": "new voice",
                    "change_reason": "test",
                },
            )

        assert response.status_code == 200
        assert response.json()["content"] == "new style"
        mock_cache.refresh.assert_called_once()


class TestVoicePreview:
    def test_503_when_no_api_key(self):
        app, _ = _create_app()

        with patch("app.api.admin.tts_persona.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                TTS_API_KEY="", TTS_BASE_URL="", TTS_VOICE_DESIGN_MODEL=""
            )
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/admin/tts/voice-preview",
                json={"voice_description": "test voice"},
            )

        assert response.status_code == 503

    def test_success(self):
        app, _ = _create_app()
        audio_bytes = b"RIFF" + b"\x00" * 10
        mock_audio = MagicMock()
        mock_audio.data = base64.b64encode(audio_bytes).decode("ascii")
        mock_choice = MagicMock()
        mock_choice.message.audio = mock_audio
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        with (
            patch("app.api.admin.tts_persona.get_settings") as mock_settings,
            patch("app.api.admin.tts_persona.AsyncOpenAI") as MockClient,
        ):
            mock_settings.return_value = MagicMock(
                TTS_API_KEY="test-key",
                TTS_BASE_URL="https://api.test.com/v1",
                TTS_VOICE_DESIGN_MODEL="mimo-v2.5-tts-voicedesign",
            )
            MockClient.return_value.chat.completions.create = AsyncMock(
                return_value=mock_completion
            )
            client = TestClient(app)
            response = client.post(
                "/api/v1/admin/tts/voice-preview",
                json={"voice_description": "test voice", "sample_text": "hello"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "wav"
        assert base64.b64decode(data["audio"]) == audio_bytes


# ---------------------------------------------------------------------------
# Repository tests (from test_tts_persona_repository.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def repo(mock_session):
    return PostgresPromptRepository(mock_session)


class TestUpdateWithVariables:
    @pytest.mark.asyncio
    async def test_updates_content_and_variables(self, repo, mock_session):
        orm = _make_prompt_orm()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = orm
        mock_session.execute = AsyncMock(side_effect=[
            mock_result,  # get_by_key
            MagicMock(scalar=MagicMock(return_value=1)),  # max version
        ])

        new_vars = [{"name": "__voice_description__", "description": "test voice"}]
        result = await repo.update_with_variables(
            key="tour_tts_persona_a",
            content="new content",
            variables=new_vars,
            changed_by="admin@test.com",
            change_reason="test update",
        )

        assert orm.content == "new content"
        assert orm.variables == new_vars
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_version(self, repo, mock_session):
        orm = _make_prompt_orm()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = orm
        mock_session.execute = AsyncMock(side_effect=[
            mock_result,
            MagicMock(scalar=MagicMock(return_value=3)),
        ])

        await repo.update_with_variables(
            key="tour_tts_persona_a",
            content="content v4",
            variables=[],
        )

        version_orm = mock_session.add.call_args[0][0]
        assert version_orm.version == 4

    @pytest.mark.asyncio
    async def test_raises_when_not_found(self, repo, mock_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(PromptNotFoundError):
            await repo.update_with_variables(
                key="nonexistent",
                content="content",
                variables=[],
            )
