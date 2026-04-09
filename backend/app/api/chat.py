import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import (
    CurrentUser,
    GuestRateLimitDep,
    LLMProviderDep,
    RagAgentDep,
    RateLimitDep,
    RedisCacheDep,
    SessionDep,
    SessionMakerDep,
)
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

router = APIRouter(prefix="/chat", tags=["chat"])

SSE_HEARTBEAT_INTERVAL = 15


async def _with_heartbeat(
    stream: AsyncGenerator[str, None],
    request: Request | None = None,
    interval: int = SSE_HEARTBEAT_INTERVAL,
) -> AsyncGenerator[str, None]:
    """Wrap an SSE stream with periodic heartbeat comments.

    Sends SSE comment lines (': heartbeat\\n\\n') at regular intervals
    to keep the connection alive through proxies and load balancers.
    Also sends an initial 'retry:' directive for client reconnection.
    """
    yield "retry: 3000\n\n"
    async for event in stream:
        yield event
        if request and await request.is_disconnected():
            return


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
    session_maker: SessionMakerDep,
    llm_provider: LLMProviderDep = None,  # type: ignore[assignment]
    rag_agent: RagAgentDep = None,  # type: ignore[assignment]
) -> StreamingResponse:
    """Stream chat response with RAG retrieval.

    The DB session lifecycle is decoupled from the SSE stream:
    - Request session is used only for ownership check
    - Streaming happens without holding a DB connection
    - Persistence uses a new short-lived session after streaming completes
    """
    chat_session = await get_session_by_id(session, ask_request.session_id, current_user["id"])
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in _with_heartbeat(
            ask_question_stream_with_rag(
                session,
                ask_request.session_id,
                ask_request.message,
                rag_agent,
                llm_provider,
                current_user["id"],
                session_maker=session_maker,
            ),
            request=request,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class MessageRequest(BaseModel):
    session_id: str | None = None
    message: str


@router.post("/guest/message")
async def send_guest_message(
    message_request: MessageRequest,
    http_request: Request,
    _: GuestRateLimitDep,
    redis: RedisCacheDep,
    rag_agent: RagAgentDep,
    llm_provider: LLMProviderDep,
) -> StreamingResponse:
    """Send a message and get streaming response (guest mode, no auth required)."""
    session_id = message_request.session_id or str(uuid.uuid4())

    return StreamingResponse(
        _with_heartbeat(
            ask_question_stream_guest(
                session_id=session_id,
                message=message_request.message,
                rag_agent=rag_agent,
                llm_provider=llm_provider,
                redis=redis,
            ),
        ),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
