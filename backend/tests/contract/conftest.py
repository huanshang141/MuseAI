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
