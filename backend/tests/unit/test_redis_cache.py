import pytest
from unittest.mock import AsyncMock
from app.infra.redis.cache import RedisCache


@pytest.mark.asyncio
async def test_get_session_context_not_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.get_session_context("session-123")
    
    assert result is None
    mock_redis.get.assert_called_once_with("session:session-123:context")


@pytest.mark.asyncio
async def test_get_session_context_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = b'[{"role": "user", "content": "hello"}]'
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.get_session_context("session-123")
    
    assert result == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_set_session_context():
    mock_redis = AsyncMock()
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    await cache.set_session_context(
        "session-123",
        [{"role": "user", "content": "hello"}],
        ttl=3600
    )
    
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_check_rate_limit_within_limit():
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 5
    mock_redis.expire = AsyncMock()
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.check_rate_limit("user-123", max_requests=60)
    
    assert result is True


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded():
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 61
    mock_redis.expire = AsyncMock()
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.check_rate_limit("user-123", max_requests=60)
    
    assert result is False
