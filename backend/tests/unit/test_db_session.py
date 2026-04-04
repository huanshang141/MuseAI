import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.infra.postgres.database import get_session_maker, get_session


@pytest.mark.asyncio
async def test_get_session():
    maker = get_session_maker("sqlite+aiosqlite:///:memory:")
    async with get_session(maker) as session:
        assert isinstance(session, AsyncSession)
