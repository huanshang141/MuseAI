"""Unit tests for chat_message_service."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.chat_message_service import (
    add_message,
    count_messages_by_session,
    get_messages_by_session,
)


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_add_message_persists_with_uuid_and_optional_trace_id():
    session = _mock_session()

    result = await add_message(
        session, session_id="s-1", role="user", content="hello", trace_id="t-1"
    )

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert added.session_id == "s-1"
    assert added.role == "user"
    assert added.content == "hello"
    assert added.trace_id == "t-1"
    assert added.id
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(added)
    assert result is added


@pytest.mark.asyncio
async def test_add_message_trace_id_defaults_to_none():
    session = _mock_session()
    result = await add_message(session, session_id="s-1", role="assistant", content="hi")
    assert result.trace_id is None


@pytest.mark.asyncio
async def test_add_message_generates_unique_ids():
    session = _mock_session()
    a = await add_message(session, session_id="s-1", role="user", content="1")
    b = await add_message(session, session_id="s-1", role="user", content="2")
    assert a.id != b.id


@pytest.mark.asyncio
async def test_get_messages_by_session_applies_limit_offset_and_asc_order():
    session = _mock_session()
    fake = [MagicMock(), MagicMock(), MagicMock()]
    scalars = MagicMock()
    scalars.all.return_value = fake
    result_obj = MagicMock()
    result_obj.scalars.return_value = scalars
    session.execute.return_value = result_obj

    messages = await get_messages_by_session(session, session_id="s-1", limit=50, offset=0)

    assert messages == fake
    stmt = session.execute.call_args[0][0]
    rendered = str(stmt).lower()
    assert "select" in rendered
    assert "chat_messages" in rendered
    assert "asc" in rendered or "order by" in rendered


@pytest.mark.asyncio
async def test_count_messages_by_session_returns_count():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar.return_value = 42
    session.execute.return_value = result_obj

    assert await count_messages_by_session(session, session_id="s-1") == 42


@pytest.mark.asyncio
async def test_count_messages_by_session_returns_zero_when_null():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar.return_value = None
    session.execute.return_value = result_obj

    assert await count_messages_by_session(session, session_id="s-empty") == 0
