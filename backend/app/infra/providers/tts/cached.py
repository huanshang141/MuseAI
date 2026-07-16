"""Redis-backed caching wrapper for TTS providers.

    Caches synthesized audio keyed by (mode, text, voice, style) so streaming
    PCM16 chunks can never be reused as a standalone WAV (or vice versa).

Falls through to the upstream provider on any Redis error (fail-open).
"""

import base64
import hashlib
import json
from collections.abc import AsyncGenerator

from loguru import logger
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig, require_valid_wav

_KEY_PREFIX = "tts:"
_DEFAULT_TTL = 3600  # 1 hour
_STREAM_MODE = "stream:pcm16"
_FILE_MODE = "file:wav"


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
    def _cache_key(text: str, config: TTSConfig, mode: str) -> str:
        raw = json.dumps(
            {
                "mode": mode,
                "style": config.style or "",
                "text": text,
                "voice": config.voice,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return _KEY_PREFIX + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def _discard_invalid_cache(self, key: str, reason: Exception | str) -> None:
        logger.warning("Ignoring invalid TTS cache entry key={} reason={}", key, reason)
        try:
            await self._redis.delete(key)
        except RedisError as exc:
            logger.debug("TTS invalid cache delete failed: {}", exc)

    async def synthesize_stream(
        self, text: str, config: TTSConfig
    ) -> AsyncGenerator[str, None]:
        key = self._cache_key(text, config, _STREAM_MODE)

        # Try cache read
        try:
            data = await self._redis.get(key)
            if data is not None:
                try:
                    chunks = json.loads(data)
                    if not isinstance(chunks, list) or not chunks:
                        raise ValueError("PCM16 cache payload must be a non-empty JSON list")
                    for chunk in chunks:
                        if not isinstance(chunk, str) or not base64.b64decode(chunk, validate=True):
                            raise ValueError("PCM16 cache contains an invalid base64 chunk")
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    await self._discard_invalid_cache(key, exc)
                else:
                    for chunk in chunks:
                        yield chunk
                    return
        except RedisError as e:
            logger.debug("TTS cache read failed (falling through): {}", e)

        # Cache miss — synthesize and collect chunks
        chunks: list[str] = []
        async for chunk in self._inner.synthesize_stream(text, config):
            if not isinstance(chunk, str) or not base64.b64decode(chunk, validate=True):
                raise ValueError("TTS provider returned an invalid PCM16 base64 chunk")
            chunks.append(chunk)
            yield chunk

        # Write only non-empty audio. An empty list cannot be a valid hit.
        if chunks:
            try:
                await self._redis.setex(key, self._ttl, json.dumps(chunks))
            except RedisError as e:
                logger.debug("TTS cache write failed: {}", e)

    async def synthesize(self, text: str, config: TTSConfig) -> bytes:
        key = self._cache_key(text, config, _FILE_MODE)

        # Try cache read
        try:
            data = await self._redis.get(key)
            if data is not None:
                try:
                    return require_valid_wav(base64.b64decode(data, validate=True))
                except (TypeError, ValueError) as exc:
                    await self._discard_invalid_cache(key, exc)
        except RedisError as e:
            logger.debug("TTS cache read failed (falling through): {}", e)

        # Cache miss
        wav = require_valid_wav(await self._inner.synthesize(text, config))

        # Write to cache
        try:
            await self._redis.setex(key, self._ttl, base64.b64encode(wav).decode())
        except RedisError as e:
            logger.debug("TTS cache write failed: {}", e)

        return wav

    async def close(self) -> None:
        await self._inner.close()
