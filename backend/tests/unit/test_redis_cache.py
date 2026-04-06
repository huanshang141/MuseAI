from unittest.mock import AsyncMock, MagicMock

import pytest
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

    await cache.set_session_context("session-123", [{"role": "user", "content": "hello"}], ttl=3600)

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == "session:session-123:context"
    assert call_args[0][1] == 3600


@pytest.mark.asyncio
async def test_get_embedding_not_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    result = await cache.get_embedding("hash123")

    assert result is None


@pytest.mark.asyncio
async def test_get_embedding_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = b"[0.1, 0.2, 0.3]"

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    result = await cache.get_embedding("hash123")

    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_set_embedding():
    mock_redis = AsyncMock()

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    await cache.set_embedding("hash123", [0.1, 0.2, 0.3], ttl=86400)

    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_get_retrieval_not_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    result = await cache.get_retrieval("query123")

    assert result is None


@pytest.mark.asyncio
async def test_set_retrieval():
    mock_redis = AsyncMock()

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    await cache.set_retrieval("query123", [{"chunk_id": "c1"}], ttl=600)

    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_check_rate_limit_within_limit():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = False
    mock_redis.incr.return_value = 5

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    result = await cache.check_rate_limit("user-123", max_requests=60)

    assert result is True


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = False
    mock_redis.incr.return_value = 61

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    result = await cache.check_rate_limit("user-123", max_requests=60)

    assert result is False


@pytest.mark.asyncio
async def test_check_rate_limit_first_request():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    result = await cache.check_rate_limit("user-123", max_requests=60)

    assert result is True
    mock_redis.set.assert_called_once_with("rate:user-123", 1, ex=60, nx=True)


@pytest.mark.asyncio
async def test_blacklist_token():
    """Test adding token to blacklist."""
    mock_redis = MagicMock()
    mock_redis.setex = AsyncMock()

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    await cache.blacklist_token("test-jti", 3600)

    mock_redis.setex.assert_called_once_with("blacklist:test-jti", 3600, "1")


@pytest.mark.asyncio
async def test_is_token_blacklisted_true():
    """Test checking if token is blacklisted (returns True)."""
    mock_redis = MagicMock()
    mock_redis.exists = AsyncMock(return_value=1)

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    result = await cache.is_token_blacklisted("test-jti")

    assert result is True
    mock_redis.exists.assert_called_once_with("blacklist:test-jti")


@pytest.mark.asyncio
async def test_is_token_blacklisted_false():
    """Test checking if token is not blacklisted (returns False)."""
    mock_redis = MagicMock()
    mock_redis.exists = AsyncMock(return_value=0)

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    result = await cache.is_token_blacklisted("test-jti")

    assert result is False
    mock_redis.exists.assert_called_once_with("blacklist:test-jti")


@pytest.mark.asyncio
async def test_set_guest_session():
    """Test setting a guest chat session."""
    mock_redis = AsyncMock()

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    messages = [{"role": "user", "content": "Hello"}]
    await cache.set_guest_session("guest-123", messages, ttl=3600)

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert "guest:guest-123:session" in call_args[0]


@pytest.mark.asyncio
async def test_get_guest_session():
    """Test getting a guest chat session."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '[{"role": "user", "content": "Hello"}]'

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    messages = await cache.get_guest_session("guest-123")

    assert messages is not None
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_get_guest_session_not_found():
    """Test getting a non-existent guest session."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    messages = await cache.get_guest_session("nonexistent")

    assert messages is None


@pytest.mark.asyncio
async def test_delete_guest_session():
    """Test deleting a guest chat session."""
    mock_redis = AsyncMock()

    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis

    await cache.delete_guest_session("guest-123")

    mock_redis.delete.assert_called_once()
    call_args = mock_redis.delete.call_args
    assert "guest:guest-123:session" in call_args[0]
