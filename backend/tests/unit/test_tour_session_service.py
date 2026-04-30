from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.domain.exceptions import TourSessionExpired, TourSessionNotFound, TourSessionTokenMismatch
from app.infra.postgres.models import TourSessionModel


def _make_model(**overrides):
    now = datetime.now(UTC)
    defaults = dict(
        id="test-session-id",
        user_id=None,
        guest_id="guest-123",
        session_token="token-abc",
        interest_type="A",
        persona="A",
        assumption="A",
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
    defaults.update(overrides)
    model = MagicMock(spec=TourSessionModel)
    for k, v in defaults.items():
        setattr(model, k, v)
    model.to_entity.return_value = MagicMock(
        id=MagicMock(value=defaults["id"]),
        user_id=None,
        guest_id=defaults["guest_id"],
        session_token=defaults["session_token"],
        interest_type=defaults["interest_type"],
        persona=defaults["persona"],
        assumption=defaults["assumption"],
        current_hall=defaults["current_hall"],
        current_exhibit_id=defaults["current_exhibit_id"],
        visited_halls=defaults["visited_halls"],
        visited_exhibit_ids=defaults["visited_exhibit_ids"],
        status=defaults["status"],
        last_active_at=defaults["last_active_at"],
        started_at=defaults["started_at"],
        completed_at=defaults["completed_at"],
        created_at=defaults["created_at"],
    )
    return model


@pytest.mark.asyncio
async def test_create_session():
    from app.application.tour_session_service import create_session

    mock_session = AsyncMock()
    model = _make_model()
    mock_session.get.return_value = None
    mock_session.add.return_value = None
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None

    with patch("app.application.tour_session_service.TourSessionModel", return_value=model):
        await create_session(
            mock_session,
            interest_type="A",
            persona="B",
            assumption="C",
            guest_id="guest-new",
        )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_session_found():
    from app.application.tour_session_service import get_session

    model = _make_model()
    mock_session = AsyncMock()
    mock_session.get.return_value = model

    await get_session(mock_session, "test-session-id")

    mock_session.get.assert_called_once_with(TourSessionModel, "test-session-id")


@pytest.mark.asyncio
async def test_get_session_not_found():
    from app.application.tour_session_service import get_session

    mock_session = AsyncMock()
    mock_session.get.return_value = None

    with pytest.raises(TourSessionNotFound):
        await get_session(mock_session, "nonexistent-id")


@pytest.mark.asyncio
async def test_get_session_expired():
    from app.application.tour_session_service import get_session

    expired_time = datetime.now(UTC) - timedelta(hours=25)
    model = _make_model(last_active_at=expired_time)
    mock_session = AsyncMock()
    mock_session.get.return_value = model

    with pytest.raises(TourSessionExpired):
        await get_session(mock_session, "test-session-id")


@pytest.mark.asyncio
async def test_update_session():
    from app.application.tour_session_service import update_session

    model = _make_model()
    mock_session = AsyncMock()
    mock_session.get.return_value = model
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None

    await update_session(
        mock_session,
        "test-session-id",
        current_hall="relic-hall",
        status="touring",
    )

    assert model.current_hall == "relic-hall"
    assert model.status == "touring"
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_session_ignores_disallowed_fields():
    from app.application.tour_session_service import update_session

    model = _make_model()
    mock_session = AsyncMock()
    mock_session.get.return_value = model
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None

    original_token = model.session_token
    await update_session(
        mock_session,
        "test-session-id",
        session_token="tampered",
        status="touring",
    )

    assert model.session_token == original_token
    assert model.status == "touring"


@pytest.mark.asyncio
async def test_update_session_allows_persona_fields():
    from app.application.tour_session_service import update_session

    model = _make_model()
    mock_session = AsyncMock()
    mock_session.get.return_value = model
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None

    await update_session(
        mock_session,
        "test-session-id",
        persona="C",
        interest_type="B",
        assumption="C",
    )

    assert model.persona == "C"
    assert model.interest_type == "B"
    assert model.assumption == "C"


@pytest.mark.asyncio
async def test_verify_session_token_valid():
    from app.application.tour_session_service import verify_session_token

    model = _make_model(session_token="correct-token")
    mock_session = AsyncMock()
    mock_session.get.return_value = model
    mock_session.commit.return_value = None

    result = await verify_session_token(mock_session, "test-session-id", "correct-token")

    assert result is not None


@pytest.mark.asyncio
async def test_verify_session_token_mismatch():
    from app.application.tour_session_service import verify_session_token

    model = _make_model(session_token="correct-token")
    mock_session = AsyncMock()
    mock_session.get.return_value = model

    with pytest.raises(TourSessionTokenMismatch):
        await verify_session_token(mock_session, "test-session-id", "wrong-token")


@pytest.mark.asyncio
async def test_verify_session_token_not_found():
    from app.application.tour_session_service import verify_session_token

    mock_session = AsyncMock()
    mock_session.get.return_value = None

    with pytest.raises(TourSessionNotFound):
        await verify_session_token(mock_session, "nonexistent-id", "any-token")


@pytest.mark.asyncio
async def test_find_active_session_by_user():
    from app.application.tour_session_service import find_active_session_by_user

    model = _make_model()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = model
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    result = await find_active_session_by_user(mock_session, "user-123")

    assert result is not None


@pytest.mark.asyncio
async def test_find_active_session_by_user_none():
    from app.application.tour_session_service import find_active_session_by_user

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    result = await find_active_session_by_user(mock_session, "user-123")

    assert result is None


@pytest.mark.asyncio
async def test_find_active_session_by_guest():
    from app.application.tour_session_service import find_active_session_by_guest

    model = _make_model()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = model
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    result = await find_active_session_by_guest(mock_session, "guest-123")

    assert result is not None
