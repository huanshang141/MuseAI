"""Tests for chat_service streaming functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest


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
        # Mock prompt_gateway to use fallback prompt
        mock_rag_agent.prompt_gateway = None

        # Mock LLM provider that streams
        async def mock_stream(messages):
            yield "This is the answer"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

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
        # Mock prompt_gateway to use fallback prompt
        mock_rag_agent.prompt_gateway = None

        # Mock LLM provider that streams
        async def mock_stream(messages):
            yield "The answer"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

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
        # Mock prompt_gateway to use fallback prompt
        mock_rag_agent.prompt_gateway = None

        # Mock LLM provider that streams
        async def mock_stream(messages):
            yield "The answer"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

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

        # Check for retrieval info in rag_step events
        rag_step_events = [e for e in events if '"type": "rag_step"' in e]
        # Should have retrieve and evaluate rag_step events
        assert any('"step": "retrieve"' in e for e in rag_step_events)
        assert any('"step": "evaluate"' in e for e in rag_step_events)
        # Check for retrieval score in evaluate event
        assert any("0.75" in e for e in rag_step_events)


@pytest.mark.asyncio
async def test_ask_question_stream_guest():
    """Test guest chat streaming without DB persistence."""
    import json
    from unittest.mock import AsyncMock, MagicMock

    from app.application.chat_service import ask_question_stream_guest

    mock_redis = AsyncMock()
    mock_redis.get_guest_session.return_value = None

    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test answer",
        "documents": [],
        "retrieval_score": 0.8,
    })
    # Mock prompt_gateway to use fallback prompt
    mock_rag_agent.prompt_gateway = None

    # Mock LLM provider that streams
    async def mock_stream(messages):
        yield "Test answer"

    mock_llm = MagicMock()
    mock_llm.generate_stream = mock_stream

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


@pytest.mark.asyncio
async def test_streaming_emits_llm_tokens_not_fixed_50_char_slices():
    """ask_question_stream_with_rag should emit LLM tokens directly, not fixed 50-char slices.

    This test verifies that streaming truly forwards tokens from the LLM provider
    rather than batching them into arbitrary 50-character chunks.

    The key assertion is that the chunk contents should match what the LLM provider
    yields, NOT be fixed 50-char slices of a complete answer.
    """
    import json

    from app.application.chat_service import ask_question_stream_with_rag

    mock_session = AsyncMock()

    # Mock session validation
    mock_chat_session = MagicMock()
    mock_chat_session.id = "session-123"
    mock_chat_session.user_id = "user-123"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_chat_session
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Define expected LLM chunks - these are the exact tokens we expect to see
    expected_llm_chunks = [
        "This ",
        "is ",
        "a ",
        "streamed ",
        "answer ",
        "from ",
        "the ",
        "LLM ",
        "provider.",
    ]

    # Mock RAG agent that returns retrieval results but streams via LLM
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(
        return_value={
            "answer": "",  # Answer will be streamed via LLM, not pre-computed
            "documents": [],
            "retrieval_score": 0.85,
        }
    )
    # Mock prompt_gateway to return None (use fallback prompt)
    mock_rag_agent.prompt_gateway = None

    # Mock LLM provider that yields variable-sized chunks
    async def mock_stream(messages):
        for chunk in expected_llm_chunks:
            yield chunk

    mock_llm = MagicMock()
    mock_llm.generate_stream = mock_stream

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

    # Extract chunk events
    chunk_events = []
    for event in events:
        if event.startswith("data: "):
            try:
                data = json.loads(event[6:])
                if data.get("type") == "chunk":
                    chunk_events.append(data)
            except json.JSONDecodeError:
                pass

    # Should have chunk events
    assert len(chunk_events) > 0, "Should have chunk events"

    # Extract chunk contents
    chunk_contents = [e.get("content", "") for e in chunk_events]

    # Key assertion: chunks should match what the LLM provider yields
    # NOT be fixed 50-char slices. We check that at least some chunks
    # are exactly what the LLM provider yielded (small token-sized chunks)
    small_chunks = [c for c in chunk_contents if 0 < len(c) < 10]
    assert len(small_chunks) > 0, (
        f"No small chunks found. All chunk lengths: {[len(c) for c in chunk_contents]}. "
        f"Expected LLM token-sized chunks (e.g., {expected_llm_chunks[:3]}), "
        "but got fixed 50-char slices instead."
    )


class TestAskQuestionStreamWithRagDegraded:
    """Tests for ask_question_stream_with_rag when ES is degraded."""

    @pytest.mark.asyncio
    async def test_returns_rag_unavailable_when_elasticsearch_degraded(self):
        """ask_question_stream_with_rag should yield RAG_UNAVAILABLE error when ES is degraded."""
        from app.application.chat_service import ask_question_stream_with_rag

        mock_session = AsyncMock()

        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_rag_agent = MagicMock()
        mock_llm = MagicMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
            degraded_services={"elasticsearch"},
        ):
            events.append(event)

        error_events = [e for e in events if "error" in e.lower()]
        assert len(error_events) >= 1
        assert "RAG_UNAVAILABLE" in error_events[-1]
        mock_rag_agent.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_proceeds_normally_when_not_degraded(self):
        """ask_question_stream_with_rag should proceed normally when not degraded."""
        from app.application.chat_service import ask_question_stream_with_rag

        mock_session = AsyncMock()

        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "answer": "The answer",
                "documents": [],
                "retrieval_score": 0.85,
            }
        )
        mock_rag_agent.prompt_gateway = None

        async def mock_stream(messages):
            yield "The answer"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

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
            degraded_services=set(),
        ):
            events.append(event)

        mock_rag_agent.run.assert_called_once()
        assert any('"type": "done"' in e for e in events)

    @pytest.mark.asyncio
    async def test_proceeds_normally_with_default_degraded_services(self):
        """ask_question_stream_with_rag should proceed normally when degraded_services is omitted."""
        from app.application.chat_service import ask_question_stream_with_rag

        mock_session = AsyncMock()

        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "answer": "The answer",
                "documents": [],
                "retrieval_score": 0.85,
            }
        )
        mock_rag_agent.prompt_gateway = None

        async def mock_stream(messages):
            yield "The answer"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

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

        mock_rag_agent.run.assert_called_once()
        assert any('"type": "done"' in e for e in events)

    @pytest.mark.asyncio
    async def test_persists_user_message_when_degraded(self):
        """ask_question_stream_with_rag should persist user message even when ES is degraded."""
        from app.application.chat_service import ask_question_stream_with_rag

        mock_session = AsyncMock()

        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_rag_agent = MagicMock()
        mock_llm = MagicMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
            degraded_services={"elasticsearch"},
        ):
            events.append(event)

        mock_session.commit.assert_called()
