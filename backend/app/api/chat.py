from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import CurrentUser
from app.application.chat_service import (
    ask_question,
    ask_question_stream_with_rag,
    create_session,
    delete_session,
    get_messages_by_session,
    get_session_by_id,
    get_sessions_by_user,
)
from app.config.settings import get_settings
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.providers.llm import OpenAICompatibleProvider

router = APIRouter(prefix="/chat", tags=["chat"])

_session_maker: async_sessionmaker[AsyncSession] | None = None


def _get_cached_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        settings = get_settings()
        _session_maker = get_session_maker(settings.DATABASE_URL)
    return _session_maker


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


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session_maker = _get_cached_session_maker()
    async with get_session(session_maker) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

_llm_provider: OpenAICompatibleProvider | None = None


def get_llm_provider() -> OpenAICompatibleProvider:
    global _llm_provider
    if _llm_provider is None:
        settings = get_settings()
        _llm_provider = OpenAICompatibleProvider.from_settings(settings)
    return _llm_provider


def get_rag_agent():
    from app.main import get_rag_agent as _get_rag_agent

    return _get_rag_agent()


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


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(session: SessionDep, current_user: CurrentUser) -> list[SessionResponse]:
    sessions = await get_sessions_by_user(session, current_user["id"])
    return [
        SessionResponse(
            id=s.id,
            user_id=s.user_id,
            title=s.title,
            created_at=s.created_at.isoformat(),
        )
        for s in sessions
    ]


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


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(session: SessionDep, session_id: str, current_user: CurrentUser) -> list[MessageResponse]:
    chat_session = await get_session_by_id(session, session_id, current_user["id"])
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = await get_messages_by_session(session, session_id)
    return [
        MessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            trace_id=m.trace_id,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.post("/ask", response_model=AskResponse)
async def ask_endpoint(session: SessionDep, request: AskRequest, current_user: CurrentUser) -> AskResponse:
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
