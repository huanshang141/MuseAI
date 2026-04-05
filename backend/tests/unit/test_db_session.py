import pytest
from app.infra.postgres.database import get_session, get_session_maker
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_session():
    maker = get_session_maker("sqlite+aiosqlite:///:memory:")
    async with get_session(maker) as session:
        assert isinstance(session, AsyncSession)
