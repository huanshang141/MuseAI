import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api._shared_responses import SessionDeleteResponse as DeleteResponse
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
    stream_iter = stream.__aiter__()
    pending_heartbeat = asyncio.ensure_future(asyncio.sleep(interval))
    pending_event: asyncio.Task | None = None

    try:
        while True:
            if pending_event is None:
                pending_event = asyncio.ensure_future(stream_iter.__anext__())

            done, _ = await asyncio.wait(
                {pending_heartbeat, pending_event},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if pending_heartbeat in done:
                yield ": heartbeat\n\n"
                pending_heartbeat = asyncio.ensure_future(asyncio.sleep(interval))

            if pending_event in done:
                try:
                    event = pending_event.result()
                    yield event
                    if request and await request.is_disconnected():
                        return
                    pending_event = None
                except StopAsyncIteration:
                    return
    finally:
        pending_heartbeat.cancel()
        if pending_event is not None:
            pending_event.cancel()


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
    tts: bool = False
    tts_voice: str | None = None


class AskResponse(BaseModel):
    answer: str
    trace_id: str
    sources: list[Any]


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


@router.post("/sessions", response_model=SessionResponse, summary="Create chat session")
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


@router.get("/sessions", response_model=SessionListResponse, summary="List chat sessions")
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


@router.get("/sessions/{session_id}", response_model=SessionResponse, summary="Get chat session")
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


@router.delete("/sessions/{session_id}", response_model=DeleteResponse, summary="Delete chat session")
async def delete_session_endpoint(session: SessionDep, session_id: str, current_user: CurrentUser) -> DeleteResponse:
    success = await delete_session(session, session_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return DeleteResponse(status="deleted", session_id=session_id)


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse, summary="List chat messages")
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


@router.post("/ask", response_model=AskResponse, summary="Ask chat question")
async def ask_endpoint(
    session: SessionDep, request: AskRequest, current_user: CurrentUser, _: RateLimitDep
) -> AskResponse:
    result = await ask_question(session, request.session_id, request.message, current_user["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return AskResponse(**result)


@router.post("/ask/stream", summary="Ask chat question (SSE)")
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
        degraded = set()
        if hasattr(request.app.state, "degraded"):
            degraded = set(request.app.state.degraded)

        tts_provider = getattr(request.app.state, "tts_provider", None)
        tts_service = getattr(request.app.state, "tts_service", None)

        tts_config = None
        if ask_request.tts and tts_provider and tts_service:
            tts_config = tts_service.get_qa_tts_config(ask_request.tts_voice)

        async for event in _with_heartbeat(
            ask_question_stream_with_rag(
                session,
                ask_request.session_id,
                ask_request.message,
                rag_agent,
                llm_provider,
                current_user["id"],
                session_maker=session_maker,
                degraded_services=degraded,
                tts_provider=tts_provider,
                tts_config=tts_config,
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
    tts: bool = False
    tts_voice: str | None = None


@router.post("/guest/message", summary="Send guest message (SSE)")
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

    degraded = set()
    if hasattr(http_request.app.state, "degraded"):
        degraded = set(http_request.app.state.degraded)

    tts_provider = getattr(http_request.app.state, "tts_provider", None)
    tts_service = getattr(http_request.app.state, "tts_service", None)

    tts_config = None
    if message_request.tts and tts_provider and tts_service:
        tts_config = tts_service.get_qa_tts_config(message_request.tts_voice)

    return StreamingResponse(
        _with_heartbeat(
            ask_question_stream_guest(
                session_id=session_id,
                message=message_request.message,
                rag_agent=rag_agent,
                llm_provider=llm_provider,
                redis=redis,
                degraded_services=degraded,
                tts_provider=tts_provider,
                tts_config=tts_config,
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
