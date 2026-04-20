"""PERFOPS-P1-03: logs emitted during a chat SSE request must carry BOTH
request_id (from HTTP middleware) and trace_id (from chat_stream_service).
This test captures loguru output and asserts both IDs appear bound to a
log record emitted from within the chat stream handler."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.main import app
from fastapi.testclient import TestClient
from loguru import logger


@pytest.fixture
def captured_logs():
    """Capture loguru records to an in-memory sink."""
    records: list[dict] = []

    def sink(message):
        records.append(dict(message.record["extra"]))

    handler_id = logger.add(sink, level="DEBUG")
    yield records
    logger.remove(handler_id)


@pytest.fixture
def patch_chat_stream():
    """Replace the dependencies the chat-stream endpoint needs so we can
    focus on log-field assertions without hitting the real pipeline."""
    from app.api.deps import (
        get_current_user,
        get_db_session,
        get_db_session_maker,
        get_llm_provider,
        get_rag_agent,
    )

    app.dependency_overrides[get_current_user] = lambda: {"id": "u-1"}

    class _FakeSession:
        async def execute(self, *a, **k):
            from types import SimpleNamespace

            return SimpleNamespace(
                scalar_one_or_none=lambda: SimpleNamespace(id="s-1", user_id="u-1")
            )

        async def commit(self):
            return None

    class _FakePersistSession:
        def add(self, *a, **k):
            return None

        async def flush(self):
            return None

        async def refresh(self, *a, **k):
            return None

        async def commit(self):
            return None

    @asynccontextmanager
    async def _fake_session_scope():
        yield _FakePersistSession()

    def _fake_session_maker():
        return _fake_session_scope()

    app.dependency_overrides[get_db_session] = lambda: _FakeSession()
    app.dependency_overrides[get_db_session_maker] = lambda: _fake_session_maker

    mock_llm = MagicMock()

    async def _stream(messages):
        for chunk in ["Hello"]:
            yield chunk

    mock_llm.generate_stream = _stream
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm

    mock_rag = MagicMock()
    mock_rag.run = AsyncMock(
        return_value={
            "answer": "Hello",
            "documents": [],
            "reranked_documents": [],
            "retrieval_score": 0.9,
            "rewritten_query": "hi",
            "transformations": [],
        }
    )
    mock_rag.score_threshold = 0.5
    mock_rag.prompt_gateway = None
    app.dependency_overrides[get_rag_agent] = lambda: mock_rag

    yield

    for dep in (
        get_current_user,
        get_db_session,
        get_db_session_maker,
        get_llm_provider,
        get_rag_agent,
    ):
        app.dependency_overrides.pop(dep, None)


def test_request_id_and_trace_id_both_appear_in_logs(patch_chat_stream, captured_logs):
    client = TestClient(app)
    req_id = "bridge-test-req-001"

    with client.stream(
        "POST",
        "/api/v1/chat/ask/stream",
        json={"session_id": "s-1", "message": "hi"},
        headers={"X-Request-ID": req_id},
    ) as response:
        for _ in response.iter_lines():
            pass
        assert response.status_code == 200

    bridged = [
        r
        for r in captured_logs
        if r.get("request_id") == req_id and r.get("trace_id") is not None
    ]
    assert bridged, (
        f"No log record carries both request_id={req_id!r} and a trace_id. "
        f"Captured extras: {captured_logs[-5:]}"
    )
