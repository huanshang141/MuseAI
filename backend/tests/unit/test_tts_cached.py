import json
from unittest.mock import AsyncMock

import pytest
from app.infra.providers.tts.base import TTSConfig
from app.infra.providers.tts.cached import CachedTTSProvider
from redis.exceptions import RedisError


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
        import base64

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
