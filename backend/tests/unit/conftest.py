"""Unit test fixtures."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_db_session():
    """Mock DB session with execute returning a configurable chat_session."""
    session = AsyncMock()
    chat_session = MagicMock()
    chat_session.id = "session-123"
    chat_session.user_id = "user-123"
    result = MagicMock()
    result.scalar_one_or_none.return_value = chat_session
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.fixture
def mock_rag_agent():
    """Mock RAG agent with LLM and prompt_gateway."""
    agent = MagicMock()
    agent.prompt_gateway = None
    agent.ainvoke = AsyncMock(return_value={"output": "test response"})
    return agent


@pytest.fixture
def mock_auth_stack():
    """Returns (redis, jwt, credentials, request) for auth dependency tests."""
    redis = MagicMock()
    redis.is_token_blacklisted = AsyncMock(return_value=False)
    jwt = MagicMock()
    jwt.get_jti = MagicMock(return_value="jti-123")
    credentials = MagicMock()
    credentials.credentials = "test-token"
    request = MagicMock()
    request.app.state.redis_cache = MagicMock()
    request.app.state.redis_cache.is_token_blacklisted = AsyncMock(return_value=False)
    return redis, jwt, credentials, request
