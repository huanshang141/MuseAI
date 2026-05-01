from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.application.tour_report_service import (
    calculate_radar_scores,
    detect_ceramic_question,
    get_report_theme,
    select_identity_tags,
)
from app.domain.entities import TourSession
from app.domain.exceptions import TourSessionExpired, TourSessionNotFound, TourSessionTokenMismatch
from app.domain.value_objects import TourSessionId
from app.infra.postgres.models import TourEventModel, TourSessionModel


# ---------------------------------------------------------------------------
# Helpers: Tour Session Service
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers: Tour Event Service
# ---------------------------------------------------------------------------

def _make_event_model(**overrides):
    now = datetime.now(UTC)
    defaults = dict(
        id="event-id-1",
        tour_session_id="session-1",
        event_type="exhibit_view",
        exhibit_id="exhibit-1",
        hall="relic-hall",
        duration_seconds=120,
        event_meta={"key": "value"},
        created_at=now,
    )
    defaults.update(overrides)
    model = MagicMock(spec=TourEventModel)
    for k, v in defaults.items():
        setattr(model, k, v)
    model.to_entity.return_value = MagicMock(
        id=MagicMock(value=defaults["id"]),
        tour_session_id=MagicMock(value=defaults["tour_session_id"]),
        event_type=defaults["event_type"],
        exhibit_id=MagicMock(value=defaults["exhibit_id"]) if defaults["exhibit_id"] else None,
        hall=defaults["hall"],
        duration_seconds=defaults["duration_seconds"],
        metadata=defaults["event_meta"],
        created_at=defaults["created_at"],
    )
    return model


# ---------------------------------------------------------------------------
# Helpers: Tour Entities
# ---------------------------------------------------------------------------

def _make_session(**overrides):
    defaults = dict(
        id=TourSessionId("test-id"),
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
        last_active_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        completed_at=None,
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return TourSession(**defaults)


# ===================================================================
# Tour Session Service Tests
# ===================================================================

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


# ===================================================================
# Tour Event Service Tests
# ===================================================================

@pytest.mark.asyncio
async def test_record_events():
    from app.application.tour_event_service import record_events

    mock_session = AsyncMock()
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None

    events_data = [
        {
            "event_type": "exhibit_view",
            "exhibit_id": "exhibit-1",
            "hall": "relic-hall",
            "duration_seconds": 120,
        },
        {
            "event_type": "exhibit_question",
            "exhibit_id": "exhibit-1",
            "hall": "relic-hall",
            "metadata": {"question": "这是什么？"},
        },
    ]

    with patch("app.application.tour_event_service.TourEventModel") as MockModel:
        models = [_make_event_model(id=f"event-{i}") for i in range(2)]
        MockModel.side_effect = models

        result = await record_events(mock_session, "session-1", events_data)

    assert len(result) == 2
    assert mock_session.add.call_count == 2
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_record_events_empty():
    from app.application.tour_event_service import record_events

    mock_session = AsyncMock()

    result = await record_events(mock_session, "session-1", [])

    assert result == []
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_events_by_session():
    from app.application.tour_event_service import get_events_by_session

    model1 = _make_event_model(id="event-1")
    model2 = _make_event_model(id="event-2", event_type="hall_leave")

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [model1, model2]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    result = await get_events_by_session(mock_session, "session-1")

    assert len(result) == 2
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_events_by_session_empty():
    from app.application.tour_event_service import get_events_by_session

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    result = await get_events_by_session(mock_session, "session-1")

    assert result == []


@pytest.mark.asyncio
async def test_record_events_retries_on_transient_error():
    from app.application.tour_event_service import record_events

    mock_session = AsyncMock()
    call_count = 0

    async def commit_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            from sqlalchemy.exc import OperationalError
            raise OperationalError("stmt", {}, Exception("connection lost"))

    mock_session.commit = AsyncMock(side_effect=commit_side_effect)
    mock_session.refresh = AsyncMock()

    events_data = [
        {
            "event_type": "exhibit_view",
            "exhibit_id": "exhibit-1",
            "hall": "relic-hall",
            "duration_seconds": 120,
        },
    ]

    with patch("app.application.tour_event_service.TourEventModel") as MockModel:
        model = _make_event_model()
        MockModel.return_value = model

        result = await record_events(mock_session, "session-1", events_data)

    assert len(result) == 1
    assert call_count == 2


@pytest.mark.asyncio
async def test_record_events_raises_after_max_retries():
    from app.application.tour_event_service import record_events
    from sqlalchemy.exc import OperationalError

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock(
        side_effect=OperationalError("stmt", {}, Exception("connection lost"))
    )

    events_data = [
        {
            "event_type": "exhibit_view",
            "exhibit_id": "exhibit-1",
            "hall": "relic-hall",
            "duration_seconds": 120,
        },
    ]

    with patch("app.application.tour_event_service.TourEventModel") as MockModel:
        model = _make_event_model()
        MockModel.return_value = model

        with pytest.raises(OperationalError):
            await record_events(mock_session, "session-1", events_data)


# ===================================================================
# Tour Report Service Tests
# ===================================================================

def test_detect_ceramic_question_true():
    assert detect_ceramic_question("这个人面鱼纹盆是做什么的？") is True
    assert detect_ceramic_question("彩陶是怎么烧制的") is True
    assert detect_ceramic_question("尖底瓶的用途") is True


def test_detect_ceramic_question_false():
    assert detect_ceramic_question("半坡人的房屋是怎么建的？") is False
    assert detect_ceramic_question("谁是首领？") is False


def test_radar_scores_all_B():
    stats = {
        "total_duration_minutes": 10,
        "total_questions": 3,
        "total_exhibits_viewed": 2,
        "site_hall_duration_minutes": 5,
        "ceramic_questions": 0,
    }
    scores = calculate_radar_scores(stats)
    assert scores["civilization_resonance"] == 1
    assert scores["imagination_breadth"] == 1
    assert scores["history_collection"] == 1
    assert scores["life_experience"] == 1
    assert scores["ceramic_aesthetics"] == 1


def test_radar_scores_all_A():
    stats = {
        "total_duration_minutes": 45,
        "total_questions": 12,
        "total_exhibits_viewed": 7,
        "site_hall_duration_minutes": 15,
        "ceramic_questions": 1,
    }
    scores = calculate_radar_scores(stats)
    assert scores["civilization_resonance"] == 2
    assert scores["imagination_breadth"] == 2
    assert scores["history_collection"] == 2
    assert scores["life_experience"] == 2
    assert scores["ceramic_aesthetics"] == 2


def test_radar_scores_all_S():
    stats = {
        "total_duration_minutes": 90,
        "total_questions": 20,
        "total_exhibits_viewed": 15,
        "site_hall_duration_minutes": 30,
        "ceramic_questions": 5,
    }
    scores = calculate_radar_scores(stats)
    assert scores["civilization_resonance"] == 3
    assert scores["imagination_breadth"] == 3
    assert scores["history_collection"] == 3
    assert scores["life_experience"] == 3
    assert scores["ceramic_aesthetics"] == 3


def test_select_identity_tags_default():
    scores = {
        "civilization_resonance": 1,
        "imagination_breadth": 1,
        "life_experience": 1,
        "ceramic_aesthetics": 1,
    }
    tags = select_identity_tags(scores)
    assert tags == ["史前细节显微镜", "六千年前的干饭王", "史前第一眼光"]


def test_select_identity_tags_all_S():
    scores = {
        "civilization_resonance": 3,
        "imagination_breadth": 3,
        "life_experience": 3,
        "ceramic_aesthetics": 3,
    }
    tags = select_identity_tags(scores)
    assert tags[0] == "冷酷无情的地层勘探机"
    assert tags[1] == "母系氏族社交悍匪"
    assert tags[2] == "彩陶纹饰解码者"


def test_get_report_theme():
    assert get_report_theme("A") == "archaeology"
    assert get_report_theme("B") == "village"
    assert get_report_theme("C") == "homework"


# ===================================================================
# Tour Entity Tests
# ===================================================================

def test_start_tour_transitions_from_onboarding_to_opening():
    session = _make_session(status="onboarding")
    session.start_tour()
    assert session.status == "opening"


def test_start_tour_raises_from_non_onboarding():
    session = _make_session(status="touring")
    with pytest.raises(ValueError, match="Can only start tour from onboarding"):
        session.start_tour()


def test_begin_touring_transitions_from_opening():
    session = _make_session(status="opening")
    session.begin_touring()
    assert session.status == "touring"


def test_begin_touring_allows_from_touring():
    session = _make_session(status="touring")
    session.begin_touring()
    assert session.status == "touring"


def test_complete_transitions_from_touring():
    session = _make_session(status="touring")
    session.complete()
    assert session.status == "completed"
    assert session.completed_at is not None


def test_complete_raises_from_non_touring():
    session = _make_session(status="onboarding")
    with pytest.raises(ValueError, match="Can only complete from touring"):
        session.complete()


def test_touch_active_updates_last_active_at():
    session = _make_session()
    old_time = session.last_active_at
    session.touch_active()
    assert session.last_active_at >= old_time
