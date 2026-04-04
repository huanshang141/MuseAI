from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.chat_service import (
    ask_question,
    create_session,
    delete_session,
    get_messages_by_session,
    get_session_by_id,
    get_sessions_by_user,
)
from app.config.settings import get_settings
from app.infra.postgres.database import get_session, get_session_maker

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
    settings = get_settings()
    session_maker = get_session_maker(settings.DATABASE_URL)
    async with get_session(session_maker) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/sessions", response_model=SessionResponse)
async def create_session_endpoint(session: SessionDep, request: CreateSessionRequest) -> SessionResponse:
    chat_session = await create_session(session, request.title)
    return SessionResponse(
        id=chat_session.id,
        user_id=chat_session.user_id,
        title=chat_session.title,
        created_at=chat_session.created_at.isoformat(),
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(session: SessionDep) -> list[SessionResponse]:
    sessions = await get_sessions_by_user(session)
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
async def get_session_detail(session: SessionDep, session_id: str) -> SessionResponse:
    chat_session = await get_session_by_id(session, session_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        id=chat_session.id,
        user_id=chat_session.user_id,
        title=chat_session.title,
        created_at=chat_session.created_at.isoformat(),
    )


@router.delete("/sessions/{session_id}", response_model=DeleteResponse)
async def delete_session_endpoint(session: SessionDep, session_id: str) -> DeleteResponse:
    success = await delete_session(session, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return DeleteResponse(status="deleted", session_id=session_id)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(session: SessionDep, session_id: str) -> list[MessageResponse]:
    chat_session = await get_session_by_id(session, session_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = await get_messages_by_session(session, session_id)
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            trace_id=m.trace_id,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.post("/ask", response_model=AskResponse)
async def ask_endpoint(session: SessionDep, request: AskRequest) -> AskResponse:
    result = await ask_question(session, request.session_id, request.message)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return AskResponse(**result)
