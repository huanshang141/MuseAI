import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.postgres.models import ChatSession


async def create_session(session: AsyncSession, title: str, user_id: str) -> ChatSession:
    session_id = str(uuid.uuid4())
    chat_session = ChatSession(
        id=session_id,
        user_id=user_id,
        title=title,
    )
    session.add(chat_session)
    await session.flush()
    await session.refresh(chat_session)
    return chat_session


async def get_sessions_by_user(
    session: AsyncSession, user_id: str, limit: int = 20, offset: int = 0
) -> list[ChatSession]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_sessions_by_user(session: AsyncSession, user_id: str) -> int:
    stmt = select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_session_by_id(session: AsyncSession, session_id: str, user_id: str) -> ChatSession | None:
    stmt = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_session(session: AsyncSession, session_id: str, user_id: str) -> bool:
    chat_session = await get_session_by_id(session, session_id, user_id)
    if chat_session is None:
        return False
    await session.delete(chat_session)
    return True
