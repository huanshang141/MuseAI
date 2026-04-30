"""Redis-backed caching wrapper for TTS providers.

Caches synthesized audio keyed by (text, voice, style) so repeated requests
for the same content skip the upstream TTS API entirely.

Falls through to the upstream provider on any Redis error (fail-open).
"""

import base64
import hashlib
import json
from collections.abc import AsyncGenerator

from loguru import logger
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig

_KEY_PREFIX = "tts:"
_DEFAULT_TTL = 3600  # 1 hour


class CachedTTSProvider(BaseTTSProvider):
    """Wraps a TTS provider with a Redis cache.

    Audio chunks are stored per-sentence (streaming) or per-request
    (non-streaming) so that identical text+voice+style combinations
    never hit the upstream API twice within the TTL window.
    """

    def __init__(
        self,
        inner: BaseTTSProvider,
        redis: Redis,
        ttl: int = _DEFAULT_TTL,
    ):
        self._inner = inner
        self._redis = redis
        self._ttl = ttl

    @staticmethod
    def _cache_key(text: str, config: TTSConfig) -> str:
        raw = f"{text}|{config.voice}|{config.style or ''}"
        return _KEY_PREFIX + hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def synthesize_stream(
        self, text: str, config: TTSConfig
    ) -> AsyncGenerator[str, None]:
        key = self._cache_key(text, config)

        # Try cache read
        try:
            data = await self._redis.get(key)
            if data is not None:
                chunks = json.loads(data)
                for chunk in chunks:
                    yield chunk
                return
        except RedisError as e:
            logger.debug("TTS cache read failed (falling through): {}", e)

        # Cache miss — synthesize and collect chunks
        chunks: list[str] = []
        async for chunk in self._inner.synthesize_stream(text, config):
            chunks.append(chunk)
            yield chunk

        # Write to cache
        try:
            await self._redis.setex(key, self._ttl, json.dumps(chunks))
        except RedisError as e:
            logger.debug("TTS cache write failed: {}", e)

    async def synthesize(self, text: str, config: TTSConfig) -> bytes:
        key = self._cache_key(text, config)

        # Try cache read
        try:
            data = await self._redis.get(key)
            if data is not None:
                return base64.b64decode(data)
        except RedisError as e:
            logger.debug("TTS cache read failed (falling through): {}", e)

        # Cache miss
        wav = await self._inner.synthesize(text, config)

        # Write to cache
        try:
            await self._redis.setex(key, self._ttl, base64.b64encode(wav).decode())
        except RedisError as e:
            logger.debug("TTS cache write failed: {}", e)

        return wav

    async def close(self) -> None:
        await self._inner.close()
