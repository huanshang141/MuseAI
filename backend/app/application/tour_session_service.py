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
        trusted_hall_chat_history={},
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
    *,
    turn_id: str | None = None,
    subject_scope: str | None = None,
    subject_exhibit_id: str | None = None,
    clarification_required: bool = False,
) -> TourSession:
    """Merge one completed turn into the latest persisted hall history.

    The row lock avoids replacing state written while the SSE response was in
    flight. Only the target hall is changed and its 30-message bound is applied
    after the merge.
    """
    model = await get_session_model(session, session_id, for_update=True)
    completed_turn = [
        {"role": "user", "content": str(user_content)[:1000]},
        {"role": "assistant", "content": str(assistant_content)[:1000]},
    ]
    stable_turn_id = str(turn_id or "").strip()[:120] or None
    trusted_turn = [dict(message) for message in completed_turn]
    normalized_subject_scope = str(subject_scope or "").strip()
    if normalized_subject_scope not in {"hall", "single", "multi", "unknown"}:
        normalized_subject_scope = ""
    normalized_subject_exhibit_id = str(subject_exhibit_id or "").strip()[:120]
    if clarification_required:
        # A clarification did not establish an object, regardless of the
        # caller's provisional classification. Enforce the invariant at the
        # persistence boundary so contradictory trusted metadata cannot exist.
        normalized_subject_scope = "unknown"
        normalized_subject_exhibit_id = ""
    if stable_turn_id:
        for message in trusted_turn:
            message["_turn_id"] = stable_turn_id
    if normalized_subject_scope:
        for message in trusted_turn:
            message["_subject_scope"] = normalized_subject_scope
    if normalized_subject_scope == "single" and normalized_subject_exhibit_id:
        for message in trusted_turn:
            message["_subject_exhibit_id"] = normalized_subject_exhibit_id
    if clarification_required:
        # This marker is written only by the backend and never copied into the
        # display history.  It prevents a later vague input (for example "1")
        # from treating a clarification prompt as a completed answer merely
        # because the wording changed.
        trusted_turn[-1]["_clarification_required"] = True

    def turn_content_matches(messages: list[dict]) -> bool:
        if len(messages) < 2:
            return False
        return all(
            str(actual.get("role") or "") == expected["role"]
            and str(actual.get("content") or "") == expected["content"]
            for actual, expected in zip(messages[-2:], completed_turn, strict=True)
        )

    def trailing_turn_count(messages: list[dict]) -> int:
        count = 0
        end = len(messages)
        while end >= 2 and turn_content_matches(messages[:end]):
            count += 1
            end -= 2
        return count

    def append_turn(
        history_value: dict | None,
        turn: list[dict],
        *,
        should_append: bool,
    ) -> tuple[dict, bool]:
        history = dict(history_value or {})
        messages = list(history.get(hall) or [])
        if not should_append:
            return history, False
        if hall not in history and len(history) >= 9:
            oldest_hall = next(iter(history))
            history.pop(oldest_hall, None)
        messages.extend(turn)
        history[hall] = messages[-30:]
        return history, True

    display_messages = list((model.hall_chat_history or {}).get(hall) or [])
    trusted_messages = list(
        (model.trusted_hall_chat_history or {}).get(hall) or []
    )
    same_stable_turn = bool(
        stable_turn_id
        and any(
            str(message.get("_turn_id") or "") == stable_turn_id
            for message in trusted_messages
        )
    )
    if same_stable_turn:
        await session.commit()
        await session.refresh(model)
        return model.to_entity()

    display_turns = trailing_turn_count(display_messages)
    trusted_turns = trailing_turn_count(trusted_messages)
    legacy_duplicate = stable_turn_id is None and trusted_turns > 0
    display_history, display_changed = append_turn(
        model.hall_chat_history,
        completed_turn,
        should_append=not legacy_duplicate and display_turns <= trusted_turns,
    )
    trusted_history, trusted_changed = append_turn(
        model.trusted_hall_chat_history,
        trusted_turn,
        should_append=not legacy_duplicate,
    )
    if not display_changed and not trusted_changed:
        await session.commit()
        await session.refresh(model)
        return model.to_entity()
    if display_changed:
        model.hall_chat_history = display_history
    if trusted_changed:
        model.trusted_hall_chat_history = trusted_history
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
