import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import TourSession
from app.domain.exceptions import (
    TourSessionExpired,
    TourSessionNotFound,
    TourSessionStateConflict,
    TourSessionTokenMismatch,
)
from app.infra.postgres.models import TourSessionModel

SESSION_EXPIRY_HOURS = 24
SESSION_ACTIVITY_TOUCH_INTERVAL = timedelta(minutes=1)


async def create_session(
    session: AsyncSession,
    interest_type: str,
    persona: str,
    assumption: str,
    user_id: str | None = None,
    guest_id: str | None = None,
    questionnaire: dict | None = None,
    resume_state: dict | None = None,
    tour_started_at: datetime | None = None,
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
        tour_started_at=tour_started_at,
        questionnaire=questionnaire or {},
        resume_state=resume_state or {},
        hall_chat_history={},
        state_version=1,
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


async def get_session_model(
    session: AsyncSession,
    session_id: str,
    *,
    for_update: bool = False,
) -> TourSessionModel:
    if for_update:
        model = await session.get(TourSessionModel, session_id, with_for_update=True)
    else:
        model = await session.get(TourSessionModel, session_id)
    if model is None:
        raise TourSessionNotFound(f"Tour session {session_id} not found")
    _check_expiry(model)
    return model


async def update_session(
    session: AsyncSession,
    session_id: str,
    expected_state_version: int | None = None,
    **updates,
) -> TourSession:
    model = await get_session_model(session, session_id, for_update=True)
    current_version = model.state_version if isinstance(model.state_version, int) else 1
    if expected_state_version is not None and expected_state_version != current_version:
        raise TourSessionStateConflict(expected_state_version, current_version)
    allowed_fields = {
        "current_hall", "current_exhibit_id", "status", "visited_halls",
        "visited_exhibit_ids", "interest_type", "persona", "assumption",
        "tour_started_at", "questionnaire", "resume_state", "hall_chat_history",
    }
    changed = False
    for key, value in updates.items():
        if key in allowed_fields:
            if key == "tour_started_at" and model.tour_started_at is not None:
                if value != model.tour_started_at:
                    raise ValueError("tour_started_at is immutable")
                continue
            if getattr(model, key) != value:
                setattr(model, key, value)
                changed = True
    if not changed:
        # Release the row lock without advancing the OCC version. Repeated
        # frontend snapshots are common and must not create false conflicts.
        await session.commit()
        await session.refresh(model)
        return model.to_entity()
    model.state_version = current_version + 1
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
    current_version = model.state_version if isinstance(model.state_version, int) else 1
    model.state_version = current_version + 1
    model.last_active_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(model)
    return model.to_entity()


async def append_hall_chat_turn(
    session: AsyncSession,
    session_id: str,
    hall: str,
    user_content: str,
    assistant_content: str,
) -> TourSession:
    """Merge one completed turn into the latest persisted hall history.

    The row lock avoids replacing state written while the SSE response was in
    flight. Only the target hall is changed and its 30-message bound is applied
    after the merge.
    """
    model = await get_session_model(session, session_id, for_update=True)
    history = dict(model.hall_chat_history or {})
    if hall not in history and len(history) >= 9:
        oldest_hall = next(iter(history))
        history.pop(oldest_hall, None)
    messages = list(history.get(hall) or [])
    completed_turn = [
        {"role": "user", "content": str(user_content)[:1000]},
        {"role": "assistant", "content": str(assistant_content)[:1000]},
    ]
    if messages[-2:] == completed_turn:
        await session.commit()
        await session.refresh(model)
        return model.to_entity()
    messages.extend(completed_turn)
    history[hall] = messages[-30:]
    model.hall_chat_history = history
    current_version = model.state_version if isinstance(model.state_version, int) else 1
    model.state_version = current_version + 1
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
    now = datetime.now(UTC)
    last_active = model.last_active_at
    if last_active is None:
        should_touch = True
    else:
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=UTC)
        should_touch = now - last_active >= SESSION_ACTIVITY_TOUCH_INTERVAL
    if should_touch:
        model.last_active_at = now
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
