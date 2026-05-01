"""Shared mock factory functions for tests."""
from unittest.mock import AsyncMock, MagicMock


def make_mock_db_session(chat_session=None):
    """Return a mock DB session with configurable chat_session return value."""
    session = AsyncMock()
    if chat_session is None:
        chat_session = MagicMock()
        chat_session.id = "session-123"
        chat_session.user_id = "user-123"
    result = MagicMock()
    result.scalar_one_or_none.return_value = chat_session
    session.execute = AsyncMock(return_value=result)
    return session


def make_mock_redis(**overrides):
    """Return a configured Redis mock. Override any method via kwargs."""
    redis = MagicMock()
    defaults = {
        "set": AsyncMock(return_value=True),
        "get": AsyncMock(return_value=None),
        "delete": AsyncMock(return_value=True),
        "exists": AsyncMock(return_value=0),
        "incr": AsyncMock(return_value=1),
        "setex": AsyncMock(),
        "close": AsyncMock(),
        "check_rate_limit": AsyncMock(return_value=True),
        "is_token_blacklisted": AsyncMock(return_value=False),
    }
    for attr, mock in defaults.items():
        setattr(redis, attr, overrides.get(attr, mock))
    return redis


def make_mock_rag_agent(**overrides):
    """Return a mock RAG agent. Override any attribute via kwargs."""
    agent = MagicMock()
    agent.prompt_gateway = overrides.get("prompt_gateway", None)
    agent.ainvoke = AsyncMock(return_value=overrides.get("output", {"output": "test response"}))
    return agent


def make_mock_auth_stack(user_id="user-123"):
    """Return (redis, jwt, credentials, request) tuple for auth tests."""
    redis = MagicMock()
    redis.is_token_blacklisted = AsyncMock(return_value=False)
    jwt = MagicMock()
    jwt.get_jti = MagicMock(return_value="jti-123")
    credentials = MagicMock()
    credentials.credentials = "test-token"
    request = MagicMock()
    request.app.state.redis_cache = redis
    return redis, jwt, credentials, request
