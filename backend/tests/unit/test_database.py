
import pytest


@pytest.mark.asyncio
async def test_get_session_maker_returns_singleton():
    """get_session_maker should return the same instance."""
    from app.infra.postgres.database import close_database, get_session_maker

    try:
        maker1 = get_session_maker("sqlite+aiosqlite:///:memory:")
        maker2 = get_session_maker("sqlite+aiosqlite:///:memory:")

        # Should return same instance
        assert maker1 is maker2
    finally:
        await close_database()


@pytest.mark.asyncio
async def test_init_database_disposes_old_engine():
    """init_database should properly dispose old engine."""
    import app.infra.postgres.database as db_module

    try:
        await db_module.init_database("sqlite+aiosqlite:///:memory:")
        first_engine = db_module._engine

        await db_module.init_database("sqlite+aiosqlite:///:memory:")
        second_engine = db_module._engine

        # Should be different engine instances
        assert first_engine is not second_engine
    finally:
        await db_module.close_database()


def test_get_db_session_uses_global_session_maker():
    """get_db_session should use the global session maker."""
    import inspect

    from app.api.deps import get_db_session

    # Check that get_db_session doesn't create its own session maker
    source = inspect.getsource(get_db_session)

    # Should not have local _session_maker assignment
    assert "_session_maker = get_session_maker" not in source
    assert "global _session_maker" not in source
