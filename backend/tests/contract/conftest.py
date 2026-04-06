"""Shared fixtures for contract tests with proper database isolation."""

import pytest
import app.infra.postgres.database as db_module


@pytest.fixture(autouse=True)
def reset_database_globals():
    """Reset global database state before and after each test.

    This ensures tests don't share database connections or in-memory SQLite databases.
    """
    import asyncio

    # Reset before test
    if db_module._engine is not None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(db_module._engine.dispose())
        except RuntimeError:
            asyncio.run(db_module._engine.dispose())

    db_module._engine = None
    db_module._session_maker = None

    yield

    # Reset after test
    if db_module._engine is not None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(db_module._engine.dispose())
        except RuntimeError:
            asyncio.run(db_module._engine.dispose())

    db_module._engine = None
    db_module._session_maker = None


@pytest.fixture(autouse=True)
def mock_app_state(monkeypatch):
    """Mock app.state singletons for contract tests."""
    from unittest.mock import MagicMock, AsyncMock
    from app.main import app

    # Create mock singletons
    mock_es_client = MagicMock()
    mock_es_client.create_index = AsyncMock()
    mock_es_client.close = AsyncMock()
    mock_es_client.health_check = AsyncMock(return_value=True)

    # Create mock Redis client for auth rate limiting
    mock_redis_client = MagicMock()
    mock_redis_client.set = AsyncMock(return_value=True)
    mock_redis_client.incr = AsyncMock(return_value=1)
    mock_redis_client.get = AsyncMock(return_value=None)
    mock_redis_client.setex = AsyncMock()
    mock_redis_client.delete = AsyncMock()
    mock_redis_client.exists = AsyncMock(return_value=0)

    mock_redis_cache = MagicMock()
    mock_redis_cache.client = mock_redis_client
    mock_redis_cache.check_rate_limit = AsyncMock(return_value=True)
    mock_redis_cache.is_token_blacklisted = AsyncMock(return_value=False)
    mock_redis_cache.close = AsyncMock()

    mock_embeddings = MagicMock()
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_rag_agent = MagicMock()
    mock_ingestion_service = MagicMock()

    # Set up app.state
    app.state.redis_cache = mock_redis_cache
    app.state.es_client = mock_es_client
    app.state.embeddings = mock_embeddings
    app.state.llm = mock_llm
    app.state.retriever = mock_retriever
    app.state.rag_agent = mock_rag_agent
    app.state.ingestion_service = mock_ingestion_service

    yield

    # Clean up app.state
    for attr in ["redis_cache", "es_client", "embeddings", "llm", "retriever", "rag_agent", "ingestion_service"]:
        if hasattr(app.state, attr):
            delattr(app.state, attr)
