from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.application.tour_report_service import (
    _pick_one_liner,
    aggregate_stats,
    build_record_summary,
    build_reflection_summary,
    calculate_radar_scores,
    collect_qa_pairs,
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
async def test_append_hall_chat_turn_merges_latest_history_and_caps_twenty():
    from app.application.tour_session_service import append_hall_chat_turn

    existing = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": str(index)}
        for index in range(20)
    ]
    model = _make_model()
    model.hall_chat_history = {
        "site-protection-hall": [{"role": "user", "content": "保留我"}],
        "basic-exhibition-hall": existing,
    }
    model.state_version = 4
    mock_session = AsyncMock()
    mock_session.get.return_value = model

    await append_hall_chat_turn(
        mock_session,
        "test-session-id",
        "basic-exhibition-hall",
        "新问题",
        "新回答",
    )

    assert model.hall_chat_history["site-protection-hall"][0]["content"] == "保留我"
    assert len(model.hall_chat_history["basic-exhibition-hall"]) == 20
    assert model.hall_chat_history["basic-exhibition-hall"][-2:] == [
        {"role": "user", "content": "新问题"},
        {"role": "assistant", "content": "新回答"},
    ]
    assert model.state_version == 5


@pytest.mark.asyncio
async def test_append_hall_chat_turn_does_not_duplicate_frontend_synced_turn():
    from app.application.tour_session_service import append_hall_chat_turn

    completed_turn = [
        {"role": "user", "content": "同一问题"},
        {"role": "assistant", "content": "同一回答"},
    ]
    model = _make_model()
    model.hall_chat_history = {"basic-exhibition-hall": completed_turn.copy()}
    model.state_version = 8
    mock_session = AsyncMock()
    mock_session.get.return_value = model

    await append_hall_chat_turn(
        mock_session,
        "test-session-id",
        "basic-exhibition-hall",
        "同一问题",
        "同一回答",
    )

    assert model.hall_chat_history["basic-exhibition-hall"] == completed_turn
    assert model.state_version == 8


@pytest.mark.asyncio
async def test_append_hall_chat_turn_evicts_oldest_hall_when_tenth_is_added():
    from app.application.tour_session_service import append_hall_chat_turn

    model = _make_model()
    model.hall_chat_history = {
        f"hall-{index}": [{"role": "user", "content": str(index)}]
        for index in range(9)
    }
    model.state_version = 2
    mock_session = AsyncMock()
    mock_session.get.return_value = model

    await append_hall_chat_turn(
        mock_session,
        "test-session-id",
        "hall-9",
        "新展厅问题",
        "新展厅回答",
    )

    assert len(model.hall_chat_history) == 9
    assert "hall-0" not in model.hall_chat_history
    assert "hall-9" in model.hall_chat_history


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
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_session_token_throttles_activity_write_to_one_minute():
    from app.application.tour_session_service import verify_session_token

    old_active = datetime.now(UTC) - timedelta(minutes=2)
    model = _make_model(session_token="correct-token", last_active_at=old_active)
    mock_session = AsyncMock()
    mock_session.get.return_value = model

    await verify_session_token(mock_session, "test-session-id", "correct-token")

    mock_session.commit.assert_awaited_once()
    assert model.last_active_at > old_active


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
async def test_record_events_skips_existing_client_event_id():
    from app.application.tour_event_service import record_events

    mock_session = AsyncMock()
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None
    existing = _make_event_model(event_meta={"client_event_id": "dup-1"})
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [existing]
    mock_session.execute.return_value = mock_result

    events_data = [
        {
            "event_type": "exhibit_question",
            "hall": "basic-exhibition-hall",
            "metadata": {"client_event_id": "dup-1", "message": "重复问题"},
        },
        {
            "event_type": "exhibit_question",
            "hall": "basic-exhibition-hall",
            "metadata": {"client_event_id": "new-1", "message": "新问题"},
        },
    ]

    result = await record_events(mock_session, "session-1", events_data)

    assert len(result) == 1
    assert mock_session.add.call_count == 1
    mock_session.commit.assert_called_once()


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
    assert tags == ["现场观察者", "好奇提问者", "参观记录者"]


def test_select_identity_tags_all_S():
    scores = {
        "civilization_resonance": 3,
        "imagination_breadth": 3,
        "life_experience": 3,
        "ceramic_aesthetics": 3,
    }
    tags = select_identity_tags(scores)
    assert tags == ["沉浸参观者", "深度追问者", "细节发现者"]


def test_get_report_theme():
    assert get_report_theme("default") == "general"
    assert get_report_theme("A") == "archaeology"
    assert get_report_theme("B") == "field_study"
    assert get_report_theme("C") == "history_inquiry"
    assert get_report_theme("D") == "artifact_study"


def test_aggregate_stats_dedupes_same_client_question_id_only():
    base_time = datetime.now(UTC)
    session = _make_session(started_at=base_time - timedelta(minutes=5))
    events = [
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            created_at=base_time,
            event_meta={
                "client_event_id": "q-1",
                "message": "半坡的石器和骨器是做什么用的？",
                "is_ceramic_question": True,
            },
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            created_at=base_time + timedelta(seconds=1),
            event_meta={
                "client_event_id": "q-1",
                "message": "半坡的石器和骨器是做什么用的？",
                "is_ceramic_question": True,
            },
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            event_meta={"message": "半坡的石器和骨器是做什么用的？"},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            event_meta={"message": "半坡的石器和骨器是做什么用的？"},
        ).to_entity(),
    ]

    stats = aggregate_stats(events, session)

    assert stats["total_questions"] == 3
    assert stats["ceramic_questions"] == 1


def test_aggregate_stats_dedupes_frontend_question_retry_window():
    base_time = datetime.now(UTC)
    session = _make_session(started_at=base_time - timedelta(minutes=5))
    events = [
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            created_at=base_time,
            event_meta={"message": "same question"},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            created_at=base_time + timedelta(seconds=2),
            event_meta={
                "client_event_id": f"{int(base_time.timestamp() * 1000)}-question-abcd1234",
                "message": "same question",
            },
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            created_at=base_time + timedelta(seconds=40),
            event_meta={"message": "same question"},
        ).to_entity(),
    ]

    stats = aggregate_stats(events, session)

    assert stats["total_questions"] == 2


def test_aggregate_stats_counts_user_sent_messages_not_answer_events():
    session = _make_session(started_at=datetime.now(UTC) - timedelta(minutes=5))
    events = [
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            event_meta={"message": "问题一"},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="site-protection-hall",
            event_meta={"message": "问题二", "is_ceramic_question": True},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="kiln-hall",
            event_meta={"message": "问题三"},
        ).to_entity(),
        _make_event_model(
            event_type="assistant_answer",
            hall="basic-exhibition-hall",
            event_meta={"question": "问题一", "answer": "回答一"},
        ).to_entity(),
        _make_event_model(
            event_type="assistant_answer",
            hall="basic-exhibition-hall",
            event_meta={"question": "问题一", "answer": "重复回答不应重复计数"},
        ).to_entity(),
        _make_event_model(
            event_type="assistant_answer",
            hall="site-protection-hall",
            event_meta={"question": "问题二", "answer": "回答二", "is_ceramic_question": True},
        ).to_entity(),
        _make_event_model(
            event_type="assistant_answer",
            hall="kiln-hall",
            event_meta={"question": "问题三", "answer": "回答三"},
        ).to_entity(),
    ]

    stats = aggregate_stats(events, session)

    assert stats["total_questions"] == 3
    assert stats["ceramic_questions"] == 1


def test_aggregate_stats_counts_answer_events_when_question_events_missing():
    session = _make_session(started_at=datetime.now(UTC) - timedelta(minutes=5))
    events = [
        _make_event_model(
            event_type="assistant_answer",
            hall="kiln-hall",
            event_meta={
                "client_event_id": "answer-1",
                "question": "陶窑结构能说明什么烧制技术？",
                "answer": "陶窑结构能说明火候控制和通风方式。",
            },
        ).to_entity(),
        _make_event_model(
            event_type="assistant_answer",
            hall="kiln-hall",
            event_meta={
                "client_event_id": "answer-retry-1",
                "question": "陶窑结构能说明什么烧制技术？",
                "answer": "陶窑结构能说明火候控制和通风方式。",
            },
        ).to_entity(),
        _make_event_model(
            event_type="assistant_answer",
            hall="basic-exhibition-hall",
            event_meta={
                "client_event_id": "answer-2",
                "question": "石器和骨器有什么用途？",
                "answer": "它们对应加工、制作和生产分工。",
            },
        ).to_entity(),
    ]

    stats = aggregate_stats(events, session)

    assert stats["total_questions"] == 2


def test_aggregate_stats_counts_exhibit_view_without_duration():
    session = _make_session(started_at=datetime.now(UTC) - timedelta(minutes=5))
    events = [
        _make_event_model(
            event_type="exhibit_view",
            exhibit_id="exhibit-no-duration",
            hall="basic-exhibition-hall",
            duration_seconds=None,
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_view",
            exhibit_id="exhibit-with-duration",
            hall="basic-exhibition-hall",
            duration_seconds=120,
            event_meta={"client_event_id": "view-duration-1"},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_view",
            exhibit_id="exhibit-with-duration",
            hall="basic-exhibition-hall",
            duration_seconds=120,
            event_meta={"client_event_id": "view-duration-1"},
        ).to_entity(),
    ]

    stats = aggregate_stats(events, session)

    assert stats["total_exhibits_viewed"] == 2
    assert stats["most_viewed_exhibit_id"] == "exhibit-with-duration"
    assert stats["most_viewed_exhibit_duration"] == 120


def test_aggregate_stats_ignores_name_only_exhibit_view():
    session = _make_session(started_at=datetime.now(UTC) - timedelta(minutes=5))
    events = [
        _make_event_model(
            event_type="exhibit_view",
            exhibit_id=None,
            hall="basic-exhibition-hall",
            duration_seconds=30,
            event_meta={"exhibit_name": "石器工具"},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_view",
            exhibit_id=None,
            hall="basic-exhibition-hall",
            duration_seconds=20,
            event_meta={"exhibit_name": "石器工具"},
        ).to_entity(),
    ]

    stats = aggregate_stats(events, session)

    assert stats["total_exhibits_viewed"] == 0
    assert stats["most_viewed_exhibit_id"] is None
    assert stats["most_viewed_exhibit_duration"] is None


def test_aggregate_stats_uses_tour_start_and_ignores_completed_at():
    now = datetime.now(UTC)
    session = _make_session(
        started_at=now - timedelta(minutes=30),
        tour_started_at=now - timedelta(minutes=12),
        completed_at=now - timedelta(minutes=8),
    )

    stats = aggregate_stats([], session)

    assert 11.9 <= stats["total_duration_minutes"] <= 12.1


def test_aggregate_stats_never_returns_negative_live_duration():
    session = _make_session(tour_started_at=datetime.now(UTC) + timedelta(minutes=4))

    stats = aggregate_stats([], session)

    assert stats["total_duration_minutes"] == 0.0


def test_report_fallback_one_liner_never_invents_an_exhibit_visit():
    line = _pick_one_liner(
        {
            "total_duration_minutes": 0,
            "total_questions": 0,
            "total_exhibits_viewed": 0,
        },
        "default",
    )

    assert line == "这次参观记录正等待你的下一次发现"
    assert "人面鱼纹盆" not in line


def test_reflection_summary_detects_interest_shift():
    session = _make_session(persona="D", assumption="D")
    events = [
        _make_event_model(
            event_type="exhibit_question",
            hall="site-protection-hall",
            event_meta={"message": "半坡聚落的布局怎样反映社会组织？"},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="site-protection-hall",
            event_meta={"message": "壕沟和房屋分布能说明共同体规则吗？"},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_deep_dive",
            hall="site-protection-hall",
            event_meta={"exhibit_name": "地面圆形房屋遗迹"},
        ).to_entity(),
    ]

    reflection = build_reflection_summary(session, events)

    assert reflection["status"] == "shifted"
    assert "器物工艺" in reflection["change_summary"]
    assert "聚落空间" in reflection["change_summary"] or "社会组织" in reflection["change_summary"]


def test_default_reflection_does_not_invent_questionnaire_assumption():
    session = _make_session(persona="default", assumption="D")
    events = [
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            event_meta={"message": "这项判断有哪些现场证据？"},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            event_meta={"message": "展签和实物之间怎样相互印证？"},
        ).to_entity(),
    ]

    reflection = build_reflection_summary(session, events)

    assert "本次复盘按你的真实参观记录整理" in reflection["initial_assumption"]
    assert "初始问题偏向" not in reflection["initial_assumption"]


def test_reflection_summary_detects_stable_focus():
    session = _make_session(persona="D", assumption="D")
    events = [
        _make_event_model(
            event_type="exhibit_question",
            hall="kiln-hall",
            event_meta={"message": "陶器烧制工艺有哪些证据？"},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="basic-exhibition-hall",
            event_meta={"message": "彩陶纹饰和器形能说明什么用途？"},
        ).to_entity(),
    ]

    reflection = build_reflection_summary(session, events)

    assert reflection["status"] == "stable"
    assert reflection["observed_focus_key"] == "craft"
    assert reflection["observed_focus"]
    assert reflection["change_summary"]


def test_reflection_summary_insufficient_evidence():
    session = _make_session(persona="C", assumption="C")
    events = [
        _make_event_model(event_type="hall_enter", hall="basic-exhibition-hall").to_entity(),
    ]

    reflection = build_reflection_summary(session, events)

    assert reflection["status"] == "insufficient"
    assert reflection["confidence"] == 0.35
    assert reflection["observed_focus_key"] is None
    assert reflection["observed_focus"]
    assert reflection["change_summary"]


def test_report_copy_does_not_invent_legacy_museum_facts():
    session = _make_session(persona="C", assumption="B")
    events = [
        _make_event_model(
            event_type="exhibit_question",
            hall="future-real-hall",
            event_meta={"message": "这项结论有哪些现场证据？"},
        ).to_entity(),
        _make_event_model(
            event_type="exhibit_question",
            hall="future-real-hall",
            event_meta={"message": "这段说明应当怎样核对证据？"},
        ).to_entity(),
    ]
    stats = {
        "total_duration_minutes": 90,
        "total_questions": 20,
        "total_exhibits_viewed": 15,
        "site_hall_duration_minutes": 30,
        "ceramic_questions": 5,
    }
    radar_scores = calculate_radar_scores(stats)
    reflection = build_reflection_summary(
        session,
        events,
        stats=stats,
        radar_scores=radar_scores,
        hall_name_map={"future-real-hall": "馆方真实展厅"},
    )
    copy = " ".join(
        [
            _pick_one_liner(stats, session.persona),
            *select_identity_tags(radar_scores),
            *(str(value) for value in reflection.values()),
        ]
    )

    for legacy_fact in (
        "陶器",
        "骨器",
        "石器",
        "房屋",
        "壕沟",
        "作坊",
        "墓葬",
        "人面鱼纹",
        "母系",
    ):
        assert legacy_fact not in copy


# ===================================================================
# Record Summary Tests
# ===================================================================

def _qa_event(event_type, question="", answer="", hall="kiln-hall", metadata_extra=None):
    metadata = {"question": question, "answer": answer}
    metadata.update(metadata_extra or {})
    return SimpleNamespace(
        event_type=event_type,
        hall=hall,
        metadata=metadata,
    )


def test_collect_qa_pairs_keeps_answered_turns_and_dedupes_client_retries():
    events = [
        _qa_event("exhibit_question", question="半坡陶器怎么烧制？"),
        _qa_event(
            "assistant_answer",
            question="半坡陶器怎么烧制？",
            answer="通过陶窑控制火候烧制。",
            metadata_extra={"client_event_id": "answer-1"},
        ),
        # Transport retry with the same client id is ignored.
        _qa_event(
            "assistant_answer",
            question="半坡陶器怎么烧制？",
            answer="（重试重复）",
            metadata_extra={"client_event_id": "answer-1"},
        ),
        # A repeated visitor turn without a shared client id is preserved.
        _qa_event("assistant_answer", question="半坡陶器怎么烧制？", answer="（重复）"),
        # answered question in a different hall
        _qa_event(
            "assistant_answer",
            question="尖底瓶怎么用？",
            answer="重心设计便于取水。",
            hall="basic-exhibition-hall",
        ),
        # bare question with no answer is dropped
        _qa_event("exhibit_question", question="还有别的吗？", hall="basic-exhibition-hall"),
    ]

    pairs = collect_qa_pairs(events)

    assert [p["question"] for p in pairs] == ["半坡陶器怎么烧制？", "半坡陶器怎么烧制？", "尖底瓶怎么用？"]
    assert pairs[0]["answer"] == "通过陶窑控制火候烧制。"
    assert pairs[1]["answer"] == "（重复）"
    assert pairs[2]["hall"] == "basic-exhibition-hall"


def test_collect_qa_pairs_empty_without_answers():
    events = [_qa_event("exhibit_question", question="这是什么？")]
    assert collect_qa_pairs(events) == []


def test_record_summary_quotes_only_real_qa_and_database_hall_name():
    result = build_record_summary(
        [
            {
                "hall": "new-special-hall",
                "question": "这里展示什么？",
                "answer": "展示馆方新导入的代表性展品。",
            }
        ],
        hall_name_map={"new-special-hall": "馆方真实展厅"},
    )

    assert result == (
        "在馆方真实展厅，你问了“这里展示什么？”，"
        "导览记录回答：“展示馆方新导入的代表性展品”。"
    )
    assert "new-special-hall" not in result


def test_record_summary_stops_at_complete_qa_before_character_budget():
    pairs = [
        {
            "hall": "future-real-hall",
            "question": f"问题{index}" * 20,
            "answer": f"回答{index}" * 40,
        }
        for index in range(10)
    ]

    result = build_record_summary(pairs)

    assert len(result) <= 400
    assert result.endswith("。")


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
