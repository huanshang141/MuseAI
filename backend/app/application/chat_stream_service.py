import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.chat_message_service import add_message
from app.application.chat_session_service import get_session_by_id
from app.application.error_handling import sanitize_error_message
from app.application.ports.repositories import CachePort, LLMProviderPort
from app.domain.exceptions import LLMError


async def ask_question(
    session: AsyncSession, session_id: str, message: str, user_id: str
) -> dict[str, Any] | None:
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
    llm_provider: LLMProviderPort,
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
    chunks: list[str] = []

    try:
        async for chunk in llm_provider.generate_stream(messages):
            chunks.append(chunk)
            yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"

        full_content = "".join(chunks)
        await add_message(session, session_id, "user", message)
        await add_message(session, session_id, "assistant", full_content, trace_id=trace_id)
        await session.commit()

        yield f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': trace_id, 'chunks': chunks})}\n\n"
    except LLMError as e:
        sanitized = sanitize_error_message(e)
        yield f"data: {json.dumps({'type': 'error', 'code': 'LLM_ERROR', 'message': sanitized})}\n\n"
    except Exception as e:
        sanitized = sanitize_error_message(e)
        yield f"data: {json.dumps({'type': 'error', 'code': 'INTERNAL_ERROR', 'message': sanitized})}\n\n"


async def ask_question_stream_with_rag(
    session: AsyncSession,
    session_id: str,
    message: str,
    rag_agent: Any,
    llm_provider: LLMProviderPort,
    user_id: str,
    session_maker: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncGenerator[str, None]:
    chat_session = await get_session_by_id(session, session_id, user_id)
    if chat_session is None:
        yield f"data: {json.dumps({'type': 'error', 'code': 'SESSION_NOT_FOUND', 'message': 'Session not found'})}\n\n"
        return

    trace_id = str(uuid.uuid4())

    def _rag_event(step: str, status: str, message: str) -> str:
        return f"data: {json.dumps({'type': 'rag_step', 'step': step, 'status': status, 'message': message})}\n\n"

    yield _rag_event('rewrite', 'running', '正在分析查询意图...')

    try:
        result = await rag_agent.run(message)
        logger.debug(f"RAG result keys: {result.keys() if hasattr(result, 'keys') else 'N/A'}")
        logger.debug(f"documents count: {len(result.get('documents', []))}")
        logger.debug(f"reranked_documents count: {len(result.get('reranked_documents', []))}")

        rewritten_query = result.get("rewritten_query", message)
        if rewritten_query != message:
            q_msg = f'查询已优化: {rewritten_query[:50]}...'
            yield _rag_event('rewrite', 'completed', q_msg)
        else:
            yield _rag_event('rewrite', 'completed', '查询分析完成')

        yield _rag_event('retrieve', 'running', '正在检索相关文档...')

        doc_count = len(result.get("documents", []))
        retrieval_score = result.get("retrieval_score", 0)

        r_msg = f'检索完成，找到 {doc_count} 个相关文档'
        yield _rag_event('retrieve', 'completed', r_msg)

        yield _rag_event('rerank', 'running', '正在对文档进行重排序...')
        yield _rag_event('rerank', 'completed', '重排序完成')

        yield _rag_event('evaluate', 'running', '正在评估检索质量...')

        transformations = result.get("transformations", [])
        if transformations and retrieval_score < rag_agent.score_threshold:
            t_msg = f'检索评分较低({retrieval_score:.2f})，已尝试查询转换'
            yield _rag_event('transform', 'completed', t_msg)

        e_msg = f'检索评分: {retrieval_score:.2f}'
        yield _rag_event('evaluate', 'completed', e_msg)

        yield _rag_event('generate', 'running', '正在生成回答...')

        docs = result.get("reranked_documents") or result.get("documents", [])
        context = "\n\n".join(doc.page_content for doc in docs)

        prompt = None
        if hasattr(rag_agent, 'prompt_gateway') and rag_agent.prompt_gateway:
            prompt = await rag_agent.prompt_gateway.render(
                "rag_answer_generation",
                {"context": context, "query": message}
            )

        if prompt is None:
            prompt = f"""你是一个博物馆导览助手。请基于以下上下文回答用户的问题。
如果上下文中没有相关信息，请礼貌地说明无法回答，并建议用户咨询工作人员。

上下文：
{context}

用户问题：{message}

请提供准确、友好的回答："""

        messages = [{"role": "user", "content": prompt}]

        chunks: list[str] = []
        async for chunk in llm_provider.generate_stream(messages):
            chunks.append(chunk)
            yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"

        answer_content = "".join(chunks)

        if session_maker is not None:
            await persist_stream_result(
                session_maker, session_id, message, answer_content, trace_id
            )
        else:
            await add_message(session, session_id, "user", message)
            await add_message(session, session_id, "assistant", answer_content, trace_id=trace_id)
            await session.commit()

        docs = result.get("reranked_documents") or result.get("documents", [])
        logger.debug(f"Using docs count: {len(docs)}")

        has_rerank_scores = any(
            d.metadata.get("rerank_score") is not None for d in docs
        )

        if has_rerank_scores:
            docs = sorted(
                docs,
                key=lambda d: d.metadata.get("rerank_score", 0),
                reverse=True
            )
        else:
            docs = sorted(
                docs,
                key=lambda d: d.metadata.get("rrf_score", 0),
                reverse=True
            )

        sources = []
        for doc in docs:
            score = doc.metadata.get("rerank_score") or doc.metadata.get("rrf_score", 0)
            chunk_id = doc.metadata.get("chunk_id")
            source_name = doc.metadata.get("source")
            rrf_score = doc.metadata.get('rrf_score')
            rerank_score = doc.metadata.get('rerank_score')
            logger.debug(f"Doc {chunk_id}: rerank_score={rerank_score}, rrf_score={rrf_score}, source={source_name}")
            if score > 0:
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
        sanitized = sanitize_error_message(e)
        yield f"data: {json.dumps({'type': 'error', 'code': 'RAG_ERROR', 'message': sanitized})}\n\n"


async def persist_stream_result(
    session_maker: async_sessionmaker[AsyncSession],
    session_id: str,
    user_message: str,
    assistant_message: str,
    trace_id: str,
) -> None:
    from app.infra.postgres.database import get_session as get_new_session

    async with get_new_session(session_maker) as session:
        await add_message(session, session_id, "user", user_message)
        await add_message(session, session_id, "assistant", assistant_message, trace_id=trace_id)


async def ask_question_stream_guest(
    session_id: str,
    message: str,
    rag_agent: Any,
    llm_provider: LLMProviderPort,
    redis: CachePort,
) -> AsyncGenerator[str, None]:
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

        docs = result.get("reranked_documents") or result.get("documents", [])
        context = "\n\n".join(doc.page_content for doc in docs)

        prompt = None
        if hasattr(rag_agent, 'prompt_gateway') and rag_agent.prompt_gateway:
            prompt = await rag_agent.prompt_gateway.render(
                "rag_answer_generation",
                {"context": context, "query": message}
            )

        if prompt is None:
            prompt = f"""你是一个博物馆导览助手。请基于以下上下文回答用户的问题。
如果上下文中没有相关信息，请礼貌地说明无法回答，并建议用户咨询工作人员。

上下文：
{context}

用户问题：{message}

请提供准确、友好的回答："""

        messages = [{"role": "user", "content": prompt}]

        chunks: list[str] = []
        async for chunk in llm_provider.generate_stream(messages):
            chunks.append(chunk)
            yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"

        answer = "".join(chunks)

        existing_messages = await redis.get_guest_session(session_id) or []
        existing_messages.append({"role": "user", "content": message})
        existing_messages.append({"role": "assistant", "content": answer})
        await redis.set_guest_session(session_id, existing_messages, ttl=3600)

        docs = result.get("reranked_documents") or result.get("documents", [])

        has_rerank_scores = any(
            d.metadata.get("rerank_score") is not None for d in docs
        )

        if has_rerank_scores:
            docs = sorted(
                docs,
                key=lambda d: d.metadata.get("rerank_score", 0),
                reverse=True
            )
        else:
            docs = sorted(
                docs,
                key=lambda d: d.metadata.get("rrf_score", 0),
                reverse=True
            )

        sources = []
        for doc in docs:
            score = doc.metadata.get("rerank_score") or doc.metadata.get("rrf_score", 0)
            if score > 0:
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
        sanitized = sanitize_error_message(e)
        yield f"data: {json.dumps({'type': 'error', 'code': 'RAG_ERROR', 'message': sanitized})}\n\n"
