import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Callable

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.exceptions import LLMError
from app.infra.postgres.models import ChatMessage, ChatSession
from app.infra.providers.llm import LLMProvider
from app.infra.redis.cache import RedisCache


def _sanitize_error_message(error: Exception) -> str:
    """Sanitize error message for client display.

    Returns a generic message that doesn't expose internal details.
    """
    # Build detailed error context for logging
    error_type = type(error).__name__
    error_msg = str(error) if str(error) else "(no message)"

    # Include request URL for httpx errors if available
    if hasattr(error, 'request'):
        try:
            request = error.request
            error_msg = f"{error_msg} (URL: {request.url})"
        except RuntimeError:
            pass  # request property not set

    # Log the actual error for debugging
    logger.error(f"Chat service error: {error_type}: {error_msg}")

    # Return generic message
    return "An unexpected error occurred. Please try again."


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
    """Get chat sessions for a user with pagination."""
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
    """Count total sessions for a user."""
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
    """Get messages for a session with pagination."""
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
    """Count total messages for a session."""
    stmt = select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def ask_question(session: AsyncSession, session_id: str, message: str, user_id: str) -> dict[str, Any] | None:
    chat_session = await get_session_by_id(session, session_id, user_id)
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
    user_id: str,
) -> dict[str, Any] | None:
    chat_session = await get_session_by_id(session, session_id, user_id)
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
    user_id: str,
) -> AsyncGenerator[str, None]:
    chat_session = await get_session_by_id(session, session_id, user_id)
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
        sanitized = _sanitize_error_message(e)
        yield f"data: {json.dumps({'type': 'error', 'code': 'LLM_ERROR', 'message': sanitized})}\n\n"
    except Exception as e:
        sanitized = _sanitize_error_message(e)
        yield f"data: {json.dumps({'type': 'error', 'code': 'INTERNAL_ERROR', 'message': sanitized})}\n\n"


async def ask_question_stream_with_rag(
    session: AsyncSession,
    session_id: str,
    message: str,
    rag_agent: Any,
    llm_provider: LLMProvider,
    user_id: str,
    session_maker: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat response with RAG retrieval.

    Args:
        session: Request-scoped session used only for ownership check.
        session_id: Chat session ID.
        message: User message.
        rag_agent: RAG agent for retrieval and generation.
        llm_provider: LLM provider for streaming.
        user_id: User ID for authorization.
        session_maker: Session maker for creating short-lived persistence sessions.
                       If provided, persistence will use a separate session,
                       decoupling DB lifecycle from SSE stream lifecycle.

    The session lifecycle is decoupled from the SSE stream:
    1. Request session is used only for ownership check (pre-check)
    2. RAG processing and streaming happen without holding a DB connection
    3. Persistence uses a new short-lived session after streaming completes
    """
    from loguru import logger

    chat_session = await get_session_by_id(session, session_id, user_id)
    if chat_session is None:
        yield f"data: {json.dumps({'type': 'error', 'code': 'SESSION_NOT_FOUND', 'message': 'Session not found'})}\n\n"
        return

    trace_id = str(uuid.uuid4())

    def _rag_event(step: str, status: str, message: str) -> str:
        return f"data: {json.dumps({'type': 'rag_step', 'step': step, 'status': status, 'message': message})}\n\n"

    # RAG步骤：查询重写
    yield _rag_event('rewrite', 'running', '正在分析查询意图...')

    # Collect answer for persistence
    answer_content = ""

    try:
        result = await rag_agent.run(message)
        logger.debug(f"RAG result keys: {result.keys() if hasattr(result, 'keys') else 'N/A'}")
        logger.debug(f"documents count: {len(result.get('documents', []))}")
        logger.debug(f"reranked_documents count: {len(result.get('reranked_documents', []))}")

        # 查询重写完成
        rewritten_query = result.get("rewritten_query", message)
        if rewritten_query != message:
            q_msg = f'查询已优化: {rewritten_query[:50]}...'
            yield _rag_event('rewrite', 'completed', q_msg)
        else:
            yield _rag_event('rewrite', 'completed', '查询分析完成')

        # RAG步骤：文档检索
        yield _rag_event('retrieve', 'running', '正在检索相关文档...')

        doc_count = len(result.get("documents", []))
        retrieval_score = result.get("retrieval_score", 0)

        r_msg = f'检索完成，找到 {doc_count} 个相关文档'
        yield _rag_event('retrieve', 'completed', r_msg)

        # RAG步骤：重排序
        yield _rag_event('rerank', 'running', '正在对文档进行重排序...')
        yield _rag_event('rerank', 'completed', '重排序完成')

        # RAG步骤：评估检索质量
        yield _rag_event('evaluate', 'running', '正在评估检索质量...')

        # 检查是否进行了查询转换
        transformations = result.get("transformations", [])
        if transformations and retrieval_score < rag_agent.score_threshold:
            t_msg = f'检索评分较低({retrieval_score:.2f})，已尝试查询转换'
            yield _rag_event('transform', 'completed', t_msg)

        e_msg = f'检索评分: {retrieval_score:.2f}'
        yield _rag_event('evaluate', 'completed', e_msg)

        # RAG步骤：生成答案
        yield _rag_event('generate', 'running', '正在生成回答...')

        answer = result.get("answer", "")
        answer_content = answer

        for chunk in [answer[i : i + 50] for i in range(0, len(answer), 50)]:
            yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"

        # Persist messages using short-lived session if session_maker is provided
        # This decouples DB session lifecycle from SSE stream lifecycle
        if session_maker is not None:
            await persist_stream_result(
                session_maker, session_id, message, answer, trace_id
            )
        else:
            # Fallback: use request session (legacy behavior, not recommended)
            await add_message(session, session_id, "user", message)
            await add_message(session, session_id, "assistant", answer, trace_id=trace_id)
            await session.commit()

        # 优先使用rerank后的文档，按rerank分数排序
        docs = result.get("reranked_documents") or result.get("documents", [])
        logger.debug(f"Using docs count: {len(docs)}")

        # 检查是否有rerank分数
        has_rerank_scores = any(
            d.metadata.get("rerank_score") is not None for d in docs
        )

        if has_rerank_scores:
            # 按rerank分数降序排序
            docs = sorted(
                docs,
                key=lambda d: d.metadata.get("rerank_score", 0),
                reverse=True
            )
        else:
            # 按RRF分数降序排序
            docs = sorted(
                docs,
                key=lambda d: d.metadata.get("rrf_score", 0),
                reverse=True
            )

        sources = []
        for doc in docs:
            # 优先使用rerank分数，其次RRF分数
            score = doc.metadata.get("rerank_score") or doc.metadata.get("rrf_score", 0)
            chunk_id = doc.metadata.get("chunk_id")
            source_name = doc.metadata.get("source")
            rrf_score = doc.metadata.get('rrf_score')
            rerank_score = doc.metadata.get('rerank_score')
            logger.debug(f"Doc {chunk_id}: rerank_score={rerank_score}, rrf_score={rrf_score}, source={source_name}")
            if score > 0:  # 只要有分数就添加
                sources.append(
                    {
                        "chunk_id": chunk_id,
                        "score": score,
                        "source": source_name or "未知来源",
                        "content": doc.page_content[:200] if doc.page_content else "",
                    }
                )

        logger.debug(f"Final sources count: {len(sources)}")
        yield f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': trace_id, 'sources': sources})}\n\n"
    except Exception as e:
        sanitized = _sanitize_error_message(e)
        yield f"data: {json.dumps({'type': 'error', 'code': 'RAG_ERROR', 'message': sanitized})}\n\n"


async def persist_stream_result(
    session_maker: async_sessionmaker[AsyncSession],
    session_id: str,
    user_message: str,
    assistant_message: str,
    trace_id: str,
) -> None:
    """Persist chat messages using a short-lived session.

    This function creates a new session solely for persistence,
    ensuring the DB connection is released immediately after the
    transaction completes, not held open during streaming.

    Args:
        session_maker: Factory for creating new sessions.
        session_id: Chat session ID.
        user_message: User's message content.
        assistant_message: Assistant's response content.
        trace_id: Trace ID for the conversation.
    """
    from app.infra.postgres.database import get_session as get_new_session

    async with get_new_session(session_maker) as session:
        await add_message(session, session_id, "user", user_message)
        await add_message(session, session_id, "assistant", assistant_message, trace_id=trace_id)


async def ask_question_stream_guest(
    session_id: str,
    message: str,
    rag_agent: Any,
    llm_provider: LLMProvider,
    redis: RedisCache,
) -> AsyncGenerator[str, None]:
    """Stream chat response for guest users (no DB persistence)."""
    trace_id = str(uuid.uuid4())

    yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': '正在检索...'})}\n\n"

    try:
        result = await rag_agent.run(message)

        doc_count = len(result.get("documents", []))
        retrieval_score = result.get("retrieval_score", 0)

        retrieve_msg = f"检索完成，找到 {doc_count} 个相关文档"
        yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': retrieve_msg})}\n\n"

        eval_msg = f"检索评分: {retrieval_score:.2f}"
        yield f"data: {json.dumps({'type': 'thinking', 'stage': 'evaluate', 'content': eval_msg})}\n\n"

        answer = result.get("answer", "")

        for chunk in [answer[i : i + 50] for i in range(0, len(answer), 50)]:
            yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"

        # Store session context for guest (no DB persistence)
        existing_messages = await redis.get_guest_session(session_id) or []
        existing_messages.append({"role": "user", "content": message})
        existing_messages.append({"role": "assistant", "content": answer})
        await redis.set_guest_session(session_id, existing_messages, ttl=3600)

        # 优先使用rerank后的文档，按rerank分数排序
        docs = result.get("reranked_documents") or result.get("documents", [])

        # 检查是否有rerank分数
        has_rerank_scores = any(
            d.metadata.get("rerank_score") is not None for d in docs
        )

        if has_rerank_scores:
            # 按rerank分数降序排序
            docs = sorted(
                docs,
                key=lambda d: d.metadata.get("rerank_score", 0),
                reverse=True
            )
        else:
            # 按RRF分数降序排序
            docs = sorted(
                docs,
                key=lambda d: d.metadata.get("rrf_score", 0),
                reverse=True
            )

        sources = []
        for doc in docs:
            # 优先使用rerank分数，其次RRF分数
            score = doc.metadata.get("rerank_score") or doc.metadata.get("rrf_score", 0)
            if score > 0:  # 只要有分数就添加
                sources.append(
                    {
                        "chunk_id": doc.metadata.get("chunk_id"),
                        "score": score,
                        "source": doc.metadata.get("source") or "未知来源",
                        "content": doc.page_content[:200] if doc.page_content else "",
                    }
                )

        yield f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': trace_id, 'sources': sources})}\n\n"
    except Exception as e:
        sanitized = _sanitize_error_message(e)
        yield f"data: {json.dumps({'type': 'error', 'code': 'RAG_ERROR', 'message': sanitized})}\n\n"
