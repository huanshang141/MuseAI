import asyncio
from contextlib import asynccontextmanager
from typing import cast
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.infra.postgres.models import Base, User

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None
_init_lock = asyncio.Lock()


async def init_database(database_url: str) -> async_sessionmaker[AsyncSession]:
    global _engine, _session_maker
    async with _init_lock:
        if _engine is not None:
            await _engine.dispose()

        new_engine = create_async_engine(database_url, echo=False)
        async with new_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        new_maker = async_sessionmaker(new_engine, class_=AsyncSession, expire_on_commit=False)
        _engine = new_engine
        _session_maker = new_maker
        
        async with new_maker() as session:
            result = await session.execute(text("SELECT 1 FROM users WHERE id = 'user-001'"))
            if result.scalar() is None:
                user = User(id="user-001", email="test@museai.local", password_hash="mock")
                session.add(user)
                await session.commit()
        
        return _session_maker


async def close_database() -> None:
    global _engine, _session_maker
    async with _init_lock:
        if _engine is not None:
            await _engine.dispose()
            _engine = None
            _session_maker = None


def get_session_maker(database_url: str) -> async_sessionmaker[AsyncSession]:
    """
    Synchronous initialization for backward compatibility with tests.
    Note: Not thread-safe. Does not dispose existing engines on reinitialization.
    Use init_database() for production use cases.
    """
    global _engine, _session_maker
    if _session_maker is None:
        new_engine = create_async_engine(database_url, echo=False)
        new_maker = async_sessionmaker(new_engine, class_=AsyncSession, expire_on_commit=False)
        _engine = new_engine
        _session_maker = new_maker
    return cast(async_sessionmaker[AsyncSession], _session_maker)


@asynccontextmanager
async def get_session(session_maker: async_sessionmaker[AsyncSession]):
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
