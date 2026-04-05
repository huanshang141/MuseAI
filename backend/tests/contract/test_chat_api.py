import pytest
from app.api.chat import get_db_session as original_get_db_session
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base, ChatSession, User
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_USER_ID = "test-user-001"


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
            test_user = User(id=TEST_USER_ID, email="test@example.com", password_hash="test_hash")
            session.add(test_user)
            await session.commit()

        yield session


@pytest.fixture
async def auth_token(db_session):
    """Get a valid JWT token for the test user."""
    from app.infra.security.jwt_handler import JWTHandler
    from app.config.settings import get_settings

    settings = get_settings()
    jwt_handler = JWTHandler(
        secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        expire_minutes=settings.JWT_EXPIRE_MINUTES,
    )
    return jwt_handler.create_token(TEST_USER_ID)


@pytest.mark.asyncio
async def test_create_session(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/sessions",
                json={"title": "新会话"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "新会话"
        assert "id" in data
        assert data["user_id"] == TEST_USER_ID
        assert "created_at" in data
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_list_sessions(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        await db_session.execute(delete(ChatSession))
        await db_session.commit()

        from app.application.chat_service import create_session

        await create_session(db_session, "会话1", TEST_USER_ID)
        await create_session(db_session, "会话2", TEST_USER_ID)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/chat/sessions",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "会话2"
        assert data[1]["title"] == "会话1"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_session(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        from app.application.chat_service import create_session

        session_obj = await create_session(db_session, "测试会话", TEST_USER_ID)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/chat/sessions/{session_obj.id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_obj.id
        assert data["title"] == "测试会话"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_session_not_found(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/chat/sessions/nonexistent-id",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_session(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        from app.application.chat_service import create_session

        session_obj = await create_session(db_session, "待删除会话", TEST_USER_ID)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/chat/sessions/{session_obj.id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/chat/sessions/{session_obj.id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_session_not_found(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                "/api/v1/chat/sessions/nonexistent-id",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_messages(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        from app.application.chat_service import add_message, create_session

        session_obj = await create_session(db_session, "消息测试", TEST_USER_ID)
        await add_message(db_session, session_obj.id, "user", "这是问题")
        await add_message(db_session, session_obj.id, "assistant", "这是回答", trace_id="trace-123")
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/chat/sessions/{session_obj.id}/messages",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[0]["content"] == "这是问题"
        assert data[0]["session_id"] == session_obj.id
        assert data[1]["role"] == "assistant"
        assert data[1]["content"] == "这是回答"
        assert data[1]["trace_id"] == "trace-123"
        assert data[1]["session_id"] == session_obj.id
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_messages_session_not_found(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/chat/sessions/nonexistent-id/messages",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_ask_question(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        from app.application.chat_service import create_session

        session_obj = await create_session(db_session, "问答测试", TEST_USER_ID)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/ask",
                json={"session_id": session_obj.id, "message": "这件青铜器是做什么用的？"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "trace_id" in data
        assert "sources" in data
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_ask_question_session_not_found(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/ask",
                json={"session_id": "nonexistent-id", "message": "问题"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}
