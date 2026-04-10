"""Unit tests for guest chat rate limiting."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.deps import (
    get_llm_provider as original_get_llm_provider,
)
from app.api.deps import (
    get_rag_agent as original_get_rag_agent,
)
from app.api.deps import (
    get_redis_cache as original_get_redis_cache,
)
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_guest_message_returns_429_when_guest_limit_exceeded():
    """Test that guest rate limit returns 429 when exceeded."""
    # Create a mock Redis cache that simulates rate limit exceeded
    mock_redis = AsyncMock()
    # Return True for first 20 requests, then False
    call_count = 0

    async def mock_check_rate_limit(key: str, max_requests: int = 60) -> bool:
        nonlocal call_count
        call_count += 1
        return call_count <= 20

    mock_redis.check_rate_limit = mock_check_rate_limit
    mock_redis.get_guest_session = AsyncMock(return_value=None)
    mock_redis.set_guest_session = AsyncMock(return_value=None)
    mock_redis.client = AsyncMock()
    mock_redis.client.set = AsyncMock(return_value=True)
    mock_redis.client.incr = AsyncMock(return_value=1)

    # Mock RAG agent and LLM provider for guest chat
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test response",
        "documents": [],
        "retrieval_score": 0.8,
    })

    mock_llm_provider = MagicMock()

    def override_redis():
        return mock_redis

    def override_rag_agent():
        return mock_rag_agent

    def override_llm_provider():
        return mock_llm_provider

    app.dependency_overrides[original_get_redis_cache] = override_redis
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Send 21 requests, the 21st should be rate limited
            last_response = None
            for i in range(21):
                response = await client.post(
                    "/api/v1/chat/guest/message",
                    json={"message": f"hello {i}"},
                )
                last_response = response

            # The 21st request should return 429
            assert last_response.status_code == 429
            assert "rate limit" in last_response.json()["detail"].lower()
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_guest_message_allows_requests_within_limit():
    """Test that guest rate limit allows requests within the limit."""
    # Create a mock Redis cache that allows requests
    mock_redis = AsyncMock()
    mock_redis.check_rate_limit = AsyncMock(return_value=True)
    mock_redis.get_guest_session = AsyncMock(return_value=None)
    mock_redis.set_guest_session = AsyncMock(return_value=None)
    mock_redis.client = AsyncMock()
    mock_redis.client.set = AsyncMock(return_value=True)
    mock_redis.client.incr = AsyncMock(return_value=1)

    # Mock RAG agent and LLM provider for guest chat
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test response",
        "documents": [],
        "retrieval_score": 0.8,
    })

    mock_llm_provider = MagicMock()

    def override_redis():
        return mock_redis

    def override_rag_agent():
        return mock_rag_agent

    def override_llm_provider():
        return mock_llm_provider

    app.dependency_overrides[original_get_redis_cache] = override_redis
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/guest/message",
                json={"message": "hello"},
            )

            assert response.status_code == 200
            assert "X-Session-Id" in response.headers
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_guest_rate_limit_uses_client_ip():
    """Test that guest rate limiting uses client IP as the key."""
    mock_redis = AsyncMock()
    mock_redis.check_rate_limit = AsyncMock(return_value=True)
    mock_redis.get_guest_session = AsyncMock(return_value=None)
    mock_redis.set_guest_session = AsyncMock(return_value=None)
    mock_redis.client = AsyncMock()
    mock_redis.client.set = AsyncMock(return_value=True)
    mock_redis.client.incr = AsyncMock(return_value=1)

    # Mock RAG agent and LLM provider for guest chat
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test response",
        "documents": [],
        "retrieval_score": 0.8,
    })

    mock_llm_provider = MagicMock()

    def override_redis():
        return mock_redis

    def override_rag_agent():
        return mock_rag_agent

    def override_llm_provider():
        return mock_llm_provider

    app.dependency_overrides[original_get_redis_cache] = override_redis
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/chat/guest/message",
                json={"message": "hello"},
            )

            # Verify check_rate_limit was called with a guest: prefix key
            mock_redis.check_rate_limit.assert_called_once()
            call_args = mock_redis.check_rate_limit.call_args
            key = call_args[0][0] if call_args[0] else call_args[1].get("key", "")
            assert key.startswith("guest:")
    finally:
        app.dependency_overrides = {}
