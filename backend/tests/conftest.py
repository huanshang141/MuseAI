"""Global shared fixtures for all tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """SQLite in-memory async session for contract/integration tests."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    engine = create_async_engine(TEST_DATABASE_URL)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def auth_token():
    """Generate a valid JWT token for test user."""
    from app.config.settings import get_settings
    from app.infra.security.jwt_handler import JWTHandler

    settings = get_settings()
    jwt_handler = JWTHandler(
        secret=settings.jwt_secret or "test-secret-key-min-32-chars-long!!",
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.jwt_expire_minutes,
    )
    return jwt_handler.create_token("user-123")


@pytest.fixture
def admin_token():
    """Generate a valid JWT token for admin user."""
    from app.config.settings import get_settings
    from app.infra.security.jwt_handler import JWTHandler

    settings = get_settings()
    jwt_handler = JWTHandler(
        secret=settings.jwt_secret or "test-secret-key-min-32-chars-long!!",
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.jwt_expire_minutes,
    )
    return jwt_handler.create_token("admin-123")


@pytest.fixture
def mock_redis():
    """Unified Redis mock with all common methods."""
    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.incr = AsyncMock(return_value=1)
    redis.setex = AsyncMock()
    redis.close = AsyncMock()
    redis.check_rate_limit = AsyncMock(return_value=True)
    redis.is_token_blacklisted = AsyncMock(return_value=False)
    redis.get_guest_session = AsyncMock(return_value=None)
    redis.set_guest_session = AsyncMock()
    return redis
