# backend/tests/unit/test_redis_singleton.py

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_get_redis_cache_returns_singleton():
    """get_redis_cache should return the same instance from app.state."""
    from app.main import app
    from app.infra.redis.cache import RedisCache

    # Mock the app.state to have a redis_cache
    mock_cache = MagicMock(spec=RedisCache)
    app.state.redis_cache = mock_cache

    # Mock request
    mock_request = MagicMock()
    mock_request.app = app

    # Import the deps version which uses request.app.state
    from app.api.deps import get_redis_cache

    # Both calls should return the same instance
    redis1 = get_redis_cache(mock_request)
    redis2 = get_redis_cache(mock_request)

    # Should be the same instance
    assert redis1 is redis2
    assert redis1 is mock_cache


def test_redis_client_reuses_connection():
    """RedisCache should not create new Redis client on every request."""
    from app.infra.redis.cache import RedisCache
    from redis.asyncio import Redis

    cache = RedisCache("redis://localhost:6379")

    # Client should be stored
    assert hasattr(cache, 'client')
    assert isinstance(cache.client, Redis)


@pytest.mark.asyncio
async def test_redis_close_cleans_up():
    """RedisCache.close should close the connection."""
    from app.infra.redis.cache import RedisCache
    from unittest.mock import AsyncMock

    cache = RedisCache("redis://localhost:6379")
    cache.client.close = AsyncMock()

    await cache.close()

    cache.client.close.assert_called_once()


def test_deps_get_redis_cache_uses_singleton():
    """deps.get_redis_cache should return singleton from request.app.state."""
    from app.api.deps import get_redis_cache
    from app.main import app
    from app.infra.redis.cache import RedisCache

    # Mock the app.state to have a redis_cache
    mock_cache = MagicMock(spec=RedisCache)
    app.state.redis_cache = mock_cache

    # Mock the request with app reference
    mock_request = MagicMock()
    mock_request.app = app

    # deps.get_redis_cache should return the same instance
    result = get_redis_cache(mock_request)
    assert result is mock_cache
