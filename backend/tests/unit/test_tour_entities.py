from datetime import UTC, datetime

import pytest
from app.domain.entities import TourSession
from app.domain.value_objects import TourSessionId


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
