from contextlib import asynccontextmanager
from typing import cast
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_database(database_url: str) -> async_sessionmaker[AsyncSession]:
    global _engine, _session_maker
    _engine = create_async_engine(database_url, echo=False)
    _session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _session_maker


async def close_database() -> None:
    global _engine, _session_maker
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_maker = None


def get_session_maker(database_url: str) -> async_sessionmaker[AsyncSession]:
    global _engine, _session_maker
    if _session_maker is None:
        _engine = create_async_engine(database_url, echo=False)
        _session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
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
