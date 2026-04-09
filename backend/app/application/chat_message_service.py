import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.postgres.models import ChatMessage


async def add_message(
    session: AsyncSession, session_id: str, role: str, content: str, trace_id: str | None = None
) -> ChatMessage:
    message_id = str(uuid.uuid4())
    message = ChatMessage(
        id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        trace_id=trace_id,
    )
    session.add(message)
    await session.flush()
    await session.refresh(message)
    return message


async def get_messages_by_session(
    session: AsyncSession, session_id: str, limit: int = 50, offset: int = 0
) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_messages_by_session(session: AsyncSession, session_id: str) -> int:
    stmt = select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
    result = await session.execute(stmt)
    return result.scalar() or 0
