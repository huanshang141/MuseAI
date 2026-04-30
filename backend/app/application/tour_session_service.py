import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import TourSession
from app.domain.exceptions import TourSessionExpired, TourSessionNotFound, TourSessionTokenMismatch
from app.infra.postgres.models import TourSessionModel

SESSION_EXPIRY_HOURS = 24


async def create_session(
    session: AsyncSession,
    interest_type: str,
    persona: str,
    assumption: str,
    user_id: str | None = None,
    guest_id: str | None = None,
) -> TourSession:
    session_id = str(uuid.uuid4())
    session_token = secrets.token_urlsafe(48)
    now = datetime.now(UTC)

    model = TourSessionModel(
        id=session_id,
        user_id=user_id,
        guest_id=guest_id,
        session_token=session_token,
        interest_type=interest_type,
        persona=persona,
        assumption=assumption,
        current_hall=None,
        current_exhibit_id=None,
        visited_halls=[],
        visited_exhibit_ids=[],
        status="onboarding",
        last_active_at=now,
        started_at=now,
        completed_at=None,
        created_at=now,
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return model.to_entity()


async def get_session(session: AsyncSession, session_id: str) -> TourSession:
    model = await session.get(TourSessionModel, session_id)
    if model is None:
        raise TourSessionNotFound(f"Tour session {session_id} not found")
    _check_expiry(model)
    return model.to_entity()


async def get_session_model(session: AsyncSession, session_id: str) -> TourSessionModel:
    model = await session.get(TourSessionModel, session_id)
    if model is None:
        raise TourSessionNotFound(f"Tour session {session_id} not found")
    _check_expiry(model)
    return model


async def update_session(
    session: AsyncSession,
    session_id: str,
    **updates,
) -> TourSession:
    model = await get_session_model(session, session_id)
    allowed_fields = {"current_hall", "current_exhibit_id", "status", "visited_halls", "visited_exhibit_ids"}
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(model, key, value)
    model.last_active_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(model)
    return model.to_entity()


async def re_onboard_session(
    session: AsyncSession,
    session_id: str,
    interest_type: str,
    persona: str,
    assumption: str,
) -> TourSession:
    model = await get_session_model(session, session_id)
    model.interest_type = interest_type
    model.persona = persona
    model.assumption = assumption
    model.status = "onboarding"
    model.last_active_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(model)
    return model.to_entity()


async def verify_session_token(session: AsyncSession, session_id: str, token: str) -> TourSession:
    model = await session.get(TourSessionModel, session_id)
    if model is None:
        raise TourSessionNotFound(f"Tour session {session_id} not found")
    if model.session_token != token:
        raise TourSessionTokenMismatch("Session token does not match")
    _check_expiry(model)
    model.last_active_at = datetime.now(UTC)
    await session.commit()
    return model.to_entity()


async def find_active_session_by_user(session: AsyncSession, user_id: str) -> TourSession | None:
    stmt = (
        select(TourSessionModel)
        .where(TourSessionModel.user_id == user_id, TourSessionModel.status != "completed")
        .order_by(TourSessionModel.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    if model is None:
        return None
    try:
        _check_expiry(model)
    except TourSessionExpired:
        return None
    return model.to_entity()


async def find_active_session_by_guest(session: AsyncSession, guest_id: str) -> TourSession | None:
    stmt = (
        select(TourSessionModel)
        .where(TourSessionModel.guest_id == guest_id, TourSessionModel.status != "completed")
        .order_by(TourSessionModel.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    if model is None:
        return None
    try:
        _check_expiry(model)
    except TourSessionExpired:
        return None
    return model.to_entity()


def _check_expiry(model: TourSessionModel) -> None:
    if model.last_active_at:
        last_active = model.last_active_at
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=UTC)
        if datetime.now(UTC) - last_active > timedelta(hours=SESSION_EXPIRY_HOURS):
            raise TourSessionExpired(f"Tour session {model.id} has expired")
