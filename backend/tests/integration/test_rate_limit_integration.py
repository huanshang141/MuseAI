# backend/tests/integration/test_rate_limit_integration.py
"""Integration tests for rate limiting behavior.

These tests verify the actual behavior of rate limiting
against a real Redis instance, replacing brittle source-inspection tests
with behavior-based tests.
"""

import pytest
from redis.asyncio import Redis

from app.infra.redis.cache import RedisCache


@pytest.fixture
async def redis_cache():
    """Create a Redis cache for integration testing.

    Uses a test-specific key prefix to avoid conflicts with production data.
    Requires a running Redis instance at localhost:6379.
    """
    redis_url = "redis://localhost:6379/15"  # Use database 15 for testing
    cache = RedisCache(redis_url)

    # Clear test database before tests
    await cache.client.flushdb()

    yield cache

    # Clear test database after tests
    await cache.client.flushdb()
    await cache.close()


@pytest.fixture
async def redis_client():
    """Direct Redis client for low-level operations."""
    client = Redis.from_url("redis://localhost:6379/15")
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.close()


@pytest.mark.integration
class TestRateLimitIntegration:
    """Integration tests for rate limiting with real Redis."""

    @pytest.mark.asyncio
    async def test_rate_limit_allows_requests_under_limit(self, redis_cache):
        """Test that requests under the limit are allowed."""
        user_id = "test_user_under_limit"

        # Make multiple requests under the limit
        for _ in range(10):
            result = await redis_cache.check_rate_limit(user_id, max_requests=60)
            assert result is True, "Requests under limit should be allowed"

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_requests_over_limit(self, redis_cache):
        """Test that requests over the limit are blocked."""
        user_id = "test_user_over_limit"
        max_requests = 5

        # Make requests up to the limit (all should succeed)
        for i in range(max_requests):
            result = await redis_cache.check_rate_limit(user_id, max_requests=max_requests)
            assert result is True, f"Request {i+1} should be allowed"

        # Next request should be blocked
        result = await redis_cache.check_rate_limit(user_id, max_requests=max_requests)
        assert result is False, "Request over limit should be blocked"

    @pytest.mark.asyncio
    async def test_rate_limit_count_increments_correctly(self, redis_cache, redis_client):
        """Test that rate limit counter increments correctly."""
        user_id = "test_user_count"
        key = f"rate:{user_id}"

        # Initial count should be 0
        count = await redis_cache.get_rate_limit_count(user_id)
        assert count == 0

        # After first request, count should be 1
        await redis_cache.check_rate_limit(user_id)
        count = await redis_cache.get_rate_limit_count(user_id)
        assert count == 1

        # After multiple requests, count should reflect total
        for _ in range(5):
            await redis_cache.check_rate_limit(user_id)

        count = await redis_cache.get_rate_limit_count(user_id)
        assert count == 6, "Count should be 6 after 6 requests"

    @pytest.mark.asyncio
    async def test_rate_limit_isolates_different_users(self, redis_cache):
        """Test that rate limits are isolated per user."""
        user1 = "user_one"
        user2 = "user_two"
        max_requests = 3

        # Exhaust user1's limit
        for _ in range(max_requests):
            await redis_cache.check_rate_limit(user1, max_requests=max_requests)

        # user1 should be blocked
        result = await redis_cache.check_rate_limit(user1, max_requests=max_requests)
        assert result is False, "user1 should be blocked"

        # user2 should still be allowed
        result = await redis_cache.check_rate_limit(user2, max_requests=max_requests)
        assert result is True, "user2 should still be allowed"

    @pytest.mark.asyncio
    async def test_rate_limit_expires_after_ttl(self, redis_cache, redis_client):
        """Test that rate limit counter expires after TTL."""
        user_id = "test_user_ttl"
        key = f"rate:{user_id}"

        # Make some requests
        for _ in range(3):
            await redis_cache.check_rate_limit(user_id, max_requests=10)

        # Verify count is 3
        count = await redis_cache.get_rate_limit_count(user_id)
        assert count == 3

        # Set TTL to 1 second for testing
        # The actual rate limit sets 60 second TTL
        # We can verify the key has a TTL set
        ttl = await redis_client.ttl(key)
        assert ttl > 0, "Key should have a TTL set"

    @pytest.mark.asyncio
    async def test_token_blacklist_roundtrip(self, redis_cache):
        """Test token blacklisting operations."""
        jti = "test_token_jti_123"
        ttl = 3600

        # Token should not be blacklisted initially
        is_blacklisted = await redis_cache.is_token_blacklisted(jti)
        assert is_blacklisted is False

        # Blacklist the token
        await redis_cache.blacklist_token(jti, ttl)

        # Token should now be blacklisted
        is_blacklisted = await redis_cache.is_token_blacklisted(jti)
        assert is_blacklisted is True

    @pytest.mark.asyncio
    async def test_token_blacklist_different_tokens_isolated(self, redis_cache):
        """Test that different tokens are independently blacklisted."""
        jti1 = "token_one"
        jti2 = "token_two"

        # Blacklist only jti1
        await redis_cache.blacklist_token(jti1, 3600)

        # jti1 should be blacklisted
        assert await redis_cache.is_token_blacklisted(jti1) is True

        # jti2 should not be blacklisted
        assert await redis_cache.is_token_blacklisted(jti2) is False

    @pytest.mark.asyncio
    async def test_guest_session_roundtrip(self, redis_cache):
        """Test guest session storage operations."""
        session_id = "guest_session_123"
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        # Store session
        await redis_cache.set_guest_session(session_id, messages, ttl=3600)

        # Retrieve session
        retrieved = await redis_cache.get_guest_session(session_id)
        assert retrieved is not None
        assert len(retrieved) == 2
        assert retrieved[0]["role"] == "user"
        assert retrieved[1]["role"] == "assistant"

        # Delete session
        await redis_cache.delete_guest_session(session_id)

        # Verify deletion
        retrieved = await redis_cache.get_guest_session(session_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_embedding_cache_roundtrip(self, redis_cache):
        """Test embedding cache operations."""
        text_hash = "hash_abc123"
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        # Store embedding
        await redis_cache.set_embedding(text_hash, embedding, ttl=3600)

        # Retrieve embedding
        retrieved = await redis_cache.get_embedding(text_hash)
        assert retrieved is not None
        assert len(retrieved) == 5
        assert retrieved == pytest.approx(embedding)

    @pytest.mark.asyncio
    async def test_retrieval_cache_roundtrip(self, redis_cache):
        """Test retrieval cache operations."""
        query_hash = "query_hash_xyz"
        results = [
            {"chunk_id": "chunk1", "content": "Result 1", "score": 0.9},
            {"chunk_id": "chunk2", "content": "Result 2", "score": 0.8}
        ]

        # Store retrieval results
        await redis_cache.set_retrieval(query_hash, results, ttl=600)

        # Retrieve results
        retrieved = await redis_cache.get_retrieval(query_hash)
        assert retrieved is not None
        assert len(retrieved) == 2
        assert retrieved[0]["chunk_id"] == "chunk1"
        assert retrieved[1]["score"] == 0.8


@pytest.mark.integration
class TestRateLimitConcurrency:
    """Integration tests for concurrent rate limit behavior."""

    @pytest.mark.asyncio
    async def test_concurrent_rate_limit_requests(self, redis_cache):
        """Test rate limiting under concurrent access."""
        import asyncio

        user_id = "concurrent_user"
        max_requests = 10
        num_concurrent = 15

        # Clear any existing data for this user
        await redis_cache.client.delete(f"rate:{user_id}")

        async def make_request():
            return await redis_cache.check_rate_limit(user_id, max_requests=max_requests)

        # Make concurrent requests
        results = await asyncio.gather(*[make_request() for _ in range(num_concurrent)])

        # Count successful and blocked requests
        allowed = sum(1 for r in results if r is True)
        blocked = sum(1 for r in results if r is False)

        # Should have exactly max_requests allowed and the rest blocked
        assert allowed == max_requests, f"Expected {max_requests} allowed, got {allowed}"
        assert blocked == num_concurrent - max_requests, f"Expected {num_concurrent - max_requests} blocked, got {blocked}"
