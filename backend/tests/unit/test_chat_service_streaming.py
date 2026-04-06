"""Tests for chat_service streaming functions."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAskQuestionStream:
    """Tests for ask_question_stream function."""

    @pytest.mark.asyncio
    async def test_yields_sse_events_on_success(self):
        """ask_question_stream should yield SSE events."""
        from app.application.chat_service import ask_question_stream

        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock LLM provider that yields chunks
        async def mock_stream(messages):
            yield "Hello"
            yield " world"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream(
            session=mock_session,
            session_id="session-123",
            message="Hello",
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have thinking, chunk, and done events
        assert len(events) >= 3
        # Check SSE format
        assert all("data:" in e for e in events)
        # Check for done event
        assert any('"type": "done"' in e for e in events)

    @pytest.mark.asyncio
    async def test_yields_error_for_invalid_session(self):
        """ask_question_stream should yield error for invalid session."""
        from app.application.chat_service import ask_question_stream

        mock_session = AsyncMock()

        # Mock session not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_llm = MagicMock()

        events = []
        async for event in ask_question_stream(
            session=mock_session,
            session_id="nonexistent-session",
            message="Hello",
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have error event
        assert len(events) == 1
        assert "error" in events[0].lower()
        assert "SESSION_NOT_FOUND" in events[0]

    @pytest.mark.asyncio
    async def test_yields_error_on_llm_error(self):
        """ask_question_stream should yield error when LLM fails."""
        from app.application.chat_service import ask_question_stream
        from app.domain.exceptions import LLMError

        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock LLM provider that raises error
        async def mock_stream_with_error(messages):
            yield "Start"
            raise LLMError("LLM unavailable")

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream_with_error

        events = []
        async for event in ask_question_stream(
            session=mock_session,
            session_id="session-123",
            message="Hello",
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have error event
        error_events = [e for e in events if "error" in e.lower()]
        assert len(error_events) >= 1
        assert "LLM_ERROR" in error_events[-1]

    @pytest.mark.asyncio
    async def test_saves_messages_on_success(self):
        """ask_question_stream should save user and assistant messages."""
        from app.application.chat_service import ask_question_stream

        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock LLM provider
        async def mock_stream(messages):
            yield "Response"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

        # Track add calls
        added_objects = []
        mock_session.add = lambda obj: added_objects.append(obj)
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream(
            session=mock_session,
            session_id="session-123",
            message="Hello",
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have added user message and assistant message
        assert len(added_objects) >= 2


class TestAskQuestionStreamWithRag:
    """Tests for ask_question_stream_with_rag function."""

    @pytest.mark.asyncio
    async def test_yields_sse_events_with_rag(self):
        """ask_question_stream_with_rag should yield SSE events."""
        from app.application.chat_service import ask_question_stream_with_rag

        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock RAG agent
        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "answer": "This is the answer",
                "documents": [],
                "retrieval_score": 0.85,
            }
        )

        mock_llm = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have thinking, chunk, and done events
        assert len(events) >= 3
        # Check for done event
        assert any('"type": "done"' in e for e in events)

    @pytest.mark.asyncio
    async def test_yields_error_for_invalid_session(self):
        """ask_question_stream_with_rag should yield error for invalid session."""
        from app.application.chat_service import ask_question_stream_with_rag

        mock_session = AsyncMock()

        # Mock session not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_rag_agent = MagicMock()
        mock_llm = MagicMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="nonexistent-session",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have error event
        assert len(events) == 1
        assert "error" in events[0].lower()
        assert "SESSION_NOT_FOUND" in events[0]

    @pytest.mark.asyncio
    async def test_yields_error_on_rag_error(self):
        """ask_question_stream_with_rag should yield error when RAG fails."""
        from app.application.chat_service import ask_question_stream_with_rag

        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock RAG agent that raises error
        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(side_effect=Exception("RAG unavailable"))

        mock_llm = MagicMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have error event
        error_events = [e for e in events if "error" in e.lower()]
        assert len(error_events) >= 1
        assert "RAG_ERROR" in error_events[-1]

    @pytest.mark.asyncio
    async def test_includes_sources_in_done_event(self):
        """ask_question_stream_with_rag should include sources in done event."""
        from app.application.chat_service import ask_question_stream_with_rag

        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock document with metadata
        mock_doc = MagicMock()
        mock_doc.page_content = "Document content"
        mock_doc.metadata = {"chunk_id": "chunk-1", "rrf_score": 0.9}

        # Mock RAG agent with documents
        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "answer": "The answer",
                "documents": [mock_doc],
                "retrieval_score": 0.85,
            }
        )

        mock_llm = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Find done event and check for sources
        done_events = [e for e in events if '"type": "done"' in e]
        assert len(done_events) == 1
        assert "chunk-1" in done_events[0]

    @pytest.mark.asyncio
    async def test_shows_retrieval_info_in_thinking(self):
        """ask_question_stream_with_rag should show retrieval info in thinking events."""
        from app.application.chat_service import ask_question_stream_with_rag

        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock document with proper attributes for JSON serialization
        mock_doc = MagicMock()
        mock_doc.page_content = "Document content"
        mock_doc.metadata = {"chunk_id": "chunk-1", "rrf_score": 0.9}

        # Mock RAG agent with documents
        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "answer": "The answer",
                "documents": [mock_doc, mock_doc],
                "retrieval_score": 0.75,
            }
        )

        mock_llm = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Check for retrieval info in thinking events
        thinking_events = [e for e in events if '"type": "thinking"' in e]
        # Should have retrieve and evaluate thinking events
        assert any('"stage": "retrieve"' in e for e in thinking_events)
        assert any('"stage": "evaluate"' in e for e in thinking_events)
        # Check for retrieval score in evaluate event
        assert any("0.75" in e for e in thinking_events)


@pytest.mark.asyncio
async def test_ask_question_stream_guest():
    """Test guest chat streaming without DB persistence."""
    from app.application.chat_service import ask_question_stream_guest
    from unittest.mock import MagicMock, AsyncMock
    import json

    mock_redis = AsyncMock()
    mock_redis.get_guest_session.return_value = None

    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test answer",
        "documents": [],
        "retrieval_score": 0.8,
    })

    mock_llm = MagicMock()

    messages = []
    async for event in ask_question_stream_guest(
        session_id="guest-123",
        message="Hello",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        redis=mock_redis,
    ):
        messages.append(event)

    # Should have thinking and done events
    event_types = [json.loads(m.split("data: ")[1])["type"] for m in messages if m.startswith("data:")]
    assert "thinking" in event_types
    assert "done" in event_types

    # Should store session in Redis
    mock_redis.set_guest_session.assert_called()
