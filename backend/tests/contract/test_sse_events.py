import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.deps import (
    get_db_session as original_get_db_session,
    get_db_session_maker as original_get_db_session_maker,
    get_llm_provider as original_get_llm_provider,
    get_rag_agent as original_get_rag_agent,
)
from app.application.chat_service import create_session
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base, ChatMessage, User
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_USER_ID = str(uuid.uuid4())


@pytest.fixture
async def session_maker():
    return get_session_maker(TEST_DATABASE_URL)


@pytest.fixture
async def db_session(session_maker):
    async with get_session(session_maker) as session:
        engine = session_maker.kw.get("bind")
        if engine:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        existing_user = await session.execute(select(User).where(User.id == TEST_USER_ID))
        if not existing_user.scalar_one_or_none():
            test_user = User(id=TEST_USER_ID, email="test@example.com", password_hash="test_hash", role="user")
            session.add(test_user)
            await session.commit()

        yield session


@pytest.fixture
async def auth_token(db_session):
    """Create a valid JWT token for testing authenticated endpoints."""
    from app.config.settings import get_settings
    from app.infra.security.jwt_handler import JWTHandler

    settings = get_settings()
    handler = JWTHandler(
        secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        expire_minutes=settings.JWT_EXPIRE_MINUTES,
    )
    return handler.create_token(TEST_USER_ID)


def parse_sse_events(content: str) -> list[dict]:
    events = []
    for line in content.strip().split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


@pytest.mark.asyncio
async def test_stream_ask_success(db_session, session_maker, auth_token):
    async def override_get_db():
        yield db_session

    def override_get_session_maker():
        return session_maker

    session_obj = await create_session(db_session, "流式测试", TEST_USER_ID)
    await db_session.commit()

    mock_llm = AsyncMock()

    async def mock_stream(*args):
        for chunk in ["这是", "一个", "测试回答"]:
            yield chunk

    mock_llm.generate_stream = mock_stream

    mock_rag = AsyncMock()
    mock_rag.run.return_value = {
        "documents": [],
        "retrieval_score": 0.95,
        "answer": "这是一个测试回答",
    }

    def override_llm_provider():
        return mock_llm

    def override_rag_agent():
        return mock_rag

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[original_get_db_session_maker] = override_get_session_maker
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/ask/stream",
                json={"session_id": session_obj.id, "message": "问题"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        events = parse_sse_events(response.text)
        assert len(events) >= 4

        # Check for rag_step events (new format)
        rag_step_events = [e for e in events if e["type"] == "rag_step"]
        assert len(rag_step_events) >= 1

        # Check for retrieve step
        retrieve_events = [e for e in rag_step_events if e["step"] == "retrieve"]
        assert len(retrieve_events) >= 1
        assert retrieve_events[0]["status"] in ["running", "completed"]

        chunk_events = [e for e in events if e["type"] == "chunk"]
        assert len(chunk_events) >= 1
        for chunk in chunk_events:
            assert chunk["stage"] == "generate"
            assert "content" in chunk

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1
        assert "trace_id" in done_events[0]
        assert "sources" in done_events[0]
        assert isinstance(done_events[0]["sources"], list)
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_stream_ask_session_not_found(db_session, session_maker, auth_token):
    async def override_get_db():
        yield db_session

    def override_get_session_maker():
        return session_maker

    mock_llm = AsyncMock()
    mock_rag = AsyncMock()

    def override_llm_provider():
        return mock_llm

    def override_rag_agent():
        return mock_rag

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[original_get_db_session_maker] = override_get_session_maker
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/ask/stream",
                json={"session_id": "nonexistent-id", "message": "问题"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_stream_ask_llm_error(db_session, session_maker, auth_token):
    async def override_get_db():
        yield db_session

    def override_get_session_maker():
        return session_maker

    session_obj = await create_session(db_session, "错误测试", TEST_USER_ID)
    await db_session.commit()

    mock_llm = AsyncMock()

    async def error_generator(*args):
        yield "开始"
        raise Exception("LLM connection failed")
        yield "不会到达"

    mock_llm.generate_stream = error_generator

    mock_rag = AsyncMock()

    def override_llm_provider():
        return mock_llm

    def override_rag_agent():
        return mock_rag

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[original_get_db_session_maker] = override_get_session_maker
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/ask/stream",
                json={"session_id": session_obj.id, "message": "问题"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        events = parse_sse_events(response.text)

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) >= 1
        assert "code" in error_events[0]
        assert "message" in error_events[0]
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_stream_ask_saves_messages(db_session, session_maker, auth_token):
    async def override_get_db():
        yield db_session

    def override_get_session_maker():
        return session_maker

    session_obj = await create_session(db_session, "消息保存测试", TEST_USER_ID)
    await db_session.commit()

    mock_llm = AsyncMock()

    async def mock_stream(*args):
        yield "回答内容"

    mock_llm.generate_stream = mock_stream

    mock_rag = AsyncMock()
    mock_rag.run.return_value = {
        "documents": [],
        "retrieval_score": 0.9,
        "answer": "回答内容",
    }

    def override_llm_provider():
        return mock_llm

    def override_rag_agent():
        return mock_rag

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[original_get_db_session_maker] = override_get_session_maker
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/ask/stream",
                json={"session_id": session_obj.id, "message": "用户问题"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200

        stmt = select(ChatMessage).where(ChatMessage.session_id == session_obj.id)
        result = await db_session.execute(stmt)
        messages = list(result.scalars().all())

        assert len(messages) == 2
        user_msg = next((m for m in messages if m.role == "user"), None)
        assistant_msg = next((m for m in messages if m.role == "assistant"), None)

        assert user_msg is not None
        assert user_msg.content == "用户问题"

        assert assistant_msg is not None
        assert assistant_msg.content == "回答内容"
        assert assistant_msg.trace_id is not None
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_stream_ask_event_format(db_session, session_maker, auth_token):
    async def override_get_db():
        yield db_session

    def override_get_session_maker():
        return session_maker

    session_obj = await create_session(db_session, "格式测试", TEST_USER_ID)
    await db_session.commit()

    mock_llm = AsyncMock()

    async def mock_stream(*args):
        yield "内容"

    mock_llm.generate_stream = mock_stream

    mock_rag = AsyncMock()

    def override_llm_provider():
        return mock_llm

    def override_rag_agent():
        return mock_rag

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[original_get_db_session_maker] = override_get_session_maker
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/ask/stream",
                json={"session_id": session_obj.id, "message": "问题"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert "data: " in response.text
        assert "\n\n" in response.text

        lines = [line for line in response.text.split("\n") if line.startswith("data: ")]
        for line in lines:
            json_str = line[6:]
            parsed = json.loads(json_str)
            assert "type" in parsed
    finally:
        app.dependency_overrides = {}
