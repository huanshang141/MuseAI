import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import LLMError
from app.infra.postgres.models import ChatMessage, ChatSession
from app.infra.providers.llm import LLMProvider

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


async def ask_question_with_rag(
    session: AsyncSession,
    session_id: str,
    message: str,
    rag_agent: Any,
) -> dict[str, Any] | None:
    chat_session = await get_session_by_id(session, session_id)
    if chat_session is None:
        return None

    await add_message(session, session_id, "user", message)

    trace_id = str(uuid.uuid4())

    result = await rag_agent.run(message)
    answer = result.get("answer", "No answer generated")

    sources = []
    for doc in result.get("documents", []):
        sources.append(
            {
                "chunk_id": doc.metadata.get("chunk_id"),
                "content": doc.page_content[:200] if doc.page_content else "",
                "score": doc.metadata.get("rrf_score"),
            }
        )

    await add_message(session, session_id, "assistant", answer, trace_id=trace_id)

    return {
        "answer": answer,
        "trace_id": trace_id,
        "sources": sources,
    }


async def ask_question_stream(
    session: AsyncSession,
    session_id: str,
    message: str,
    llm_provider: LLMProvider,
) -> AsyncGenerator[str, None]:
    chat_session = await get_session_by_id(session, session_id)
    if chat_session is None:
        yield f"data: {json.dumps({'type': 'error', 'code': 'SESSION_NOT_FOUND', 'message': 'Session not found'})}\n\n"
        return

    trace_id = str(uuid.uuid4())

    yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': '正在检索...'})}\n\n"
    yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': '检索完成'})}\n\n"

    messages = [{"role": "user", "content": message}]
    full_content = ""
    chunks: list[str] = []

    try:
        async for chunk in llm_provider.generate_stream(messages):
            full_content += chunk
            chunks.append(chunk)
            yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"

        await add_message(session, session_id, "user", message)
        await add_message(session, session_id, "assistant", full_content, trace_id=trace_id)
        await session.commit()

        yield f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': trace_id, 'chunks': chunks})}\n\n"
    except LLMError as e:
        yield f"data: {json.dumps({'type': 'error', 'code': 'LLM_ERROR', 'message': str(e)})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'code': 'INTERNAL_ERROR', 'message': str(e)})}\n\n"


async def ask_question_stream_with_rag(
    session: AsyncSession,
    session_id: str,
    message: str,
    rag_agent: Any,
    llm_provider: LLMProvider,
) -> AsyncGenerator[str, None]:
    chat_session = await get_session_by_id(session, session_id)
    if chat_session is None:
        yield f"data: {json.dumps({'type': 'error', 'code': 'SESSION_NOT_FOUND', 'message': 'Session not found'})}\n\n"
        return

    trace_id = str(uuid.uuid4())

    yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': '正在检索...'})}\n\n"

    try:
        result = await rag_agent.run(message)

        doc_count = len(result.get("documents", []))
        retrieval_score = result.get("retrieval_score", 0)

        yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': f'检索完成，找到 {doc_count} 个相关文档'})}\n\n"
        yield f"data: {json.dumps({'type': 'thinking', 'stage': 'evaluate', 'content': f'检索评分: {retrieval_score:.2f}'})}\n\n"

        answer = result.get("answer", "")

        for chunk in [answer[i : i + 50] for i in range(0, len(answer), 50)]:
            yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"

        await add_message(session, session_id, "user", message)
        await add_message(session, session_id, "assistant", answer, trace_id=trace_id)
        await session.commit()

        sources = []
        for doc in result.get("documents", []):
            sources.append(
                {
                    "chunk_id": doc.metadata.get("chunk_id"),
                    "score": doc.metadata.get("rrf_score"),
                }
            )

        yield f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': trace_id, 'sources': sources})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'code': 'RAG_ERROR', 'message': str(e)})}\n\n"
