from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.infra.postgres.models import TourEventModel


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
