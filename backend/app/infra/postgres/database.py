import asyncio
from contextlib import asynccontextmanager
from typing import cast

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.infra.postgres.models import Base

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None
_init_lock = asyncio.Lock()

DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 10
DEFAULT_POOL_TIMEOUT = 30
DEFAULT_POOL_RECYCLE = 1800


def _get_pool_kwargs() -> dict:
    return {
        "pool_size": DEFAULT_POOL_SIZE,
        "max_overflow": DEFAULT_MAX_OVERFLOW,
        "pool_timeout": DEFAULT_POOL_TIMEOUT,
        "pool_recycle": DEFAULT_POOL_RECYCLE,
        "pool_pre_ping": True,
    }


async def init_database(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Initialize database engine and session maker.

    Thread-safe - uses lock to prevent race conditions.
    Disposes existing engine before creating new one.
    """
    global _engine, _session_maker
    async with _init_lock:
        if _engine is not None:
            await _engine.dispose()

        engine_kwargs: dict = {"echo": False}
        if "sqlite" not in database_url:
            engine_kwargs.update(_get_pool_kwargs())
        new_engine = create_async_engine(database_url, **engine_kwargs)
        async with new_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        new_maker = async_sessionmaker(new_engine, class_=AsyncSession, expire_on_commit=False)
        _engine = new_engine
        _session_maker = new_maker

        return _session_maker


async def close_database() -> None:
    """Dispose database engine and clear session maker."""
    global _engine, _session_maker
    async with _init_lock:
        if _engine is not None:
            await _engine.dispose()
            _engine = None
            _session_maker = None


def get_session_maker(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    """Get the global session maker.

    If session maker is not initialized and database_url is provided,
    creates a new one (not thread-safe, for testing only).

    For production, use init_database() instead.
    """
    global _engine, _session_maker
    if _session_maker is None:
        if database_url is None:
            raise RuntimeError("Database not initialized. Call init_database() first.")
        engine_kwargs: dict = {"echo": False}
        if "sqlite" not in database_url:
            engine_kwargs.update(_get_pool_kwargs())
        new_engine = create_async_engine(database_url, **engine_kwargs)
        new_maker = async_sessionmaker(new_engine, class_=AsyncSession, expire_on_commit=False)
        _engine = new_engine
        _session_maker = new_maker
    return cast(async_sessionmaker[AsyncSession], _session_maker)


@asynccontextmanager
async def get_session(session_maker: async_sessionmaker[AsyncSession] | None = None):
    """Get a database session.

    If session_maker is not provided, uses the global one.
    """
    if session_maker is None:
        session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
