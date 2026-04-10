# backend/tests/unit/test_chat_error_sanitization.py

from unittest.mock import AsyncMock, MagicMock

import pytest


def _mock_existing_session() -> AsyncMock:
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock(id="test-session")
    mock_session.execute.return_value = mock_result
    return mock_session


@pytest.mark.asyncio
async def test_sse_error_does_not_leak_internal_details():
    """SSE error events should not contain internal error details."""
    from app.application.chat_service import ask_question_stream_with_rag

    mock_session = _mock_existing_session()
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(side_effect=Exception("Internal error: /home/user/secret/path config.py line 42"))
    mock_llm = MagicMock()

    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="test-session",
        message="test message",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)

    # Find error event
    error_events = [e for e in events if "error" in e.lower()]
    assert len(error_events) > 0, "Should have error event"

    # Error should not contain internal paths
    for event in error_events:
        assert "/home/" not in event
        assert "config.py" not in event
        assert "line 42" not in event
        assert "Internal error" not in event


@pytest.mark.asyncio
async def test_sse_error_shows_generic_message():
    """SSE error events should show generic error message."""
    from app.application.chat_service import ask_question_stream_with_rag

    mock_session = _mock_existing_session()
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(side_effect=Exception("Database connection failed"))
    mock_llm = MagicMock()

    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="test-session",
        message="test message",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)

    error_events = [e for e in events if "error" in e.lower()]
    assert len(error_events) > 0

    # Should contain generic message
    any_has_generic = any("An error occurred" in e or "unexpected error" in e.lower() for e in error_events)
    assert any_has_generic, "Should have generic error message"
