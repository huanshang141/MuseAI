import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.postgres.models import ChatMessage, ChatSession

MOCK_USER_ID = "user-001"


async def create_session(session: AsyncSession, title: str) -> ChatSession:
    session_id = str(uuid.uuid4())
    chat_session = ChatSession(
        id=session_id,
        user_id=MOCK_USER_ID,
        title=title,
    )
    session.add(chat_session)
    await session.flush()
    await session.refresh(chat_session)
    return chat_session


async def get_sessions_by_user(session: AsyncSession) -> list[ChatSession]:
    stmt = select(ChatSession).where(ChatSession.user_id == MOCK_USER_ID).order_by(ChatSession.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_session_by_id(session: AsyncSession, session_id: str) -> ChatSession | None:
    stmt = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == MOCK_USER_ID)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_session(session: AsyncSession, session_id: str) -> bool:
    chat_session = await get_session_by_id(session, session_id)
    if chat_session is None:
        return False
    await session.delete(chat_session)
    await session.commit()
    return True


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


async def get_messages_by_session(session: AsyncSession, session_id: str) -> list[ChatMessage]:
    stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def ask_question(session: AsyncSession, session_id: str, message: str) -> dict[str, Any] | None:
    chat_session = await get_session_by_id(session, session_id)
    if chat_session is None:
        return None

    await add_message(session, session_id, "user", message)

    trace_id = str(uuid.uuid4())
    answer = "这是一个占位回答。RAG集成将在后续任务中实现。"

    await add_message(session, session_id, "assistant", answer, trace_id=trace_id)

    return {
        "answer": answer,
        "trace_id": trace_id,
        "sources": [],
    }
