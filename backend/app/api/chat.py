import sys
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import CurrentUser, RateLimitDep, RedisCacheDep, SessionDep
from app.application.chat_service import (
    ask_question,
    ask_question_stream_guest,
    ask_question_stream_with_rag,
    count_messages_by_session,
    count_sessions_by_user,
    create_session,
    delete_session,
    get_messages_by_session,
    get_session_by_id,
    get_sessions_by_user,
)
from app.config.settings import get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain import create_embeddings, create_llm, create_rag_agent, create_retriever
from app.infra.providers.llm import OpenAICompatibleProvider

router = APIRouter(prefix="/chat", tags=["chat"])


class CreateSessionRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    trace_id: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class AskRequest(BaseModel):
    session_id: str
    message: str


class AskResponse(BaseModel):
    answer: str
    trace_id: str
    sources: list[Any]


class DeleteResponse(BaseModel):
    status: str
    session_id: str


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int
    limit: int
    offset: int


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int
    limit: int
    offset: int


_llm_provider: OpenAICompatibleProvider | None = None
_rag_agent = None


def _get_app_state_attr(attr_name: str) -> Any:
    """Get attribute from app.state if available, without late import."""
    main_module = sys.modules.get("app.main")
    if main_module and hasattr(main_module, "app"):
        app = main_module.app
        if hasattr(app.state, attr_name):
            return getattr(app.state, attr_name)
    return None


def get_llm_provider() -> OpenAICompatibleProvider:
    """Get LLM provider - cached singleton that can be overridden for tests."""
    global _llm_provider
    if _llm_provider is None:
        settings = get_settings()
        _llm_provider = OpenAICompatibleProvider.from_settings(settings)
    return _llm_provider


def get_rag_agent() -> Any:
    """Get RAG agent from app.state or create fallback.

    Priority:
    1. app.state.rag_agent (set by lifespan or mocked in tests)
    2. Module-level _rag_agent fallback (created on first call)
    """
    # Check app.state first (for production and mocked tests)
    agent = _get_app_state_attr("rag_agent")
    if agent is not None:
        return agent

    # Fallback: create from settings (used in standalone mode)
    global _rag_agent
    if _rag_agent is None:
        settings = get_settings()
        es_client = ElasticsearchClient(
            hosts=[settings.ELASTICSEARCH_URL],
            index_name=settings.ELASTICSEARCH_INDEX,
        )
        embeddings = create_embeddings(settings)
        llm = create_llm(settings)
        retriever = create_retriever(es_client, embeddings, settings)
        _rag_agent = create_rag_agent(llm, retriever, settings)
    return _rag_agent


# Dependency types (must be defined after get_rag_agent and get_llm_provider)
RagAgentDep = Annotated[Any, Depends(get_rag_agent)]
LLMProviderDep = Annotated[OpenAICompatibleProvider, Depends(get_llm_provider)]


@router.post("/sessions", response_model=SessionResponse)
async def create_session_endpoint(
    session: SessionDep, request: CreateSessionRequest, current_user: CurrentUser
) -> SessionResponse:
    chat_session = await create_session(session, request.title, current_user["id"])
    return SessionResponse(
        id=chat_session.id,
        user_id=chat_session.user_id,
        title=chat_session.title,
        created_at=chat_session.created_at.isoformat(),
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    session: SessionDep,
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> SessionListResponse:
    sessions = await get_sessions_by_user(session, current_user["id"], limit=limit, offset=offset)
    total = await count_sessions_by_user(session, current_user["id"])
    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=s.id,
                user_id=s.user_id,
                title=s.title,
                created_at=s.created_at.isoformat(),
            )
            for s in sessions
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session_detail(session: SessionDep, session_id: str, current_user: CurrentUser) -> SessionResponse:
    chat_session = await get_session_by_id(session, session_id, current_user["id"])
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        id=chat_session.id,
        user_id=chat_session.user_id,
        title=chat_session.title,
        created_at=chat_session.created_at.isoformat(),
    )


@router.delete("/sessions/{session_id}", response_model=DeleteResponse)
async def delete_session_endpoint(session: SessionDep, session_id: str, current_user: CurrentUser) -> DeleteResponse:
    success = await delete_session(session, session_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return DeleteResponse(status="deleted", session_id=session_id)


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def get_session_messages(
    session: SessionDep,
    session_id: str,
    current_user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> MessageListResponse:
    chat_session = await get_session_by_id(session, session_id, current_user["id"])
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = await get_messages_by_session(session, session_id, limit=limit, offset=offset)
    total = await count_messages_by_session(session, session_id)
    return MessageListResponse(
        messages=[
            MessageResponse(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                trace_id=m.trace_id,
                created_at=m.created_at.isoformat(),
            )
            for m in messages
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/ask", response_model=AskResponse)
async def ask_endpoint(
    session: SessionDep, request: AskRequest, current_user: CurrentUser, _: RateLimitDep
) -> AskResponse:
    result = await ask_question(session, request.session_id, request.message, current_user["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return AskResponse(**result)


@router.post("/ask/stream")
async def ask_stream_endpoint(
    request: Request,
    session: SessionDep,
    ask_request: AskRequest,
    current_user: CurrentUser,
    _: RateLimitDep,
) -> StreamingResponse:
    chat_session = await get_session_by_id(session, ask_request.session_id, current_user["id"])
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    llm_provider = get_llm_provider()
    rag_agent = get_rag_agent()

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in ask_question_stream_with_rag(
            session, ask_request.session_id, ask_request.message, rag_agent, llm_provider, current_user["id"]
        ):
            if await request.is_disconnected():
                break
            yield event

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class MessageRequest(BaseModel):
    session_id: str | None = None
    message: str


@router.post("/guest/message")
async def send_guest_message(
    request: MessageRequest,
    redis: RedisCacheDep,
    rag_agent: RagAgentDep,
    llm_provider: LLMProviderDep,
) -> StreamingResponse:
    """Send a message and get streaming response (guest mode, no auth required)."""
    session_id = request.session_id or str(uuid.uuid4())

    return StreamingResponse(
        ask_question_stream_guest(
            session_id=session_id,
            message=request.message,
            rag_agent=rag_agent,
            llm_provider=llm_provider,
            redis=redis,
        ),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
