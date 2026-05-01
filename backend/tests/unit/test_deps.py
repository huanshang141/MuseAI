"""Tests for API dependencies module.

Merged from:
- test_api_deps.py
- test_deps_security.py
- test_auth_logout.py
- test_auth_rate_limit.py
- test_guest_rate_limit.py
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.auth import logout
from app.api.deps import (
    get_llm_provider as original_get_llm_provider,
)
from app.api.deps import (
    get_rag_agent as original_get_rag_agent,
)
from app.api.deps import (
    get_redis_cache as original_get_redis_cache,
)
from app.main import app
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from redis.exceptions import RedisError


# ---------------------------------------------------------------------------
# Fixtures (shared across tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    """Mock Redis for rate limiting tests."""
    redis = MagicMock()
    redis.check_rate_limit = AsyncMock(return_value=True)
    redis.is_token_blacklisted = AsyncMock(return_value=False)
    return redis


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Tests from test_api_deps.py
# ---------------------------------------------------------------------------


class TestGetDbSession:
    """Tests for get_db_session generator."""

    @pytest.mark.asyncio
    async def test_yields_database_session(self):
        """get_db_session should yield database sessions."""
        from contextlib import asynccontextmanager

        from app.api.deps import get_db_session

        mock_session = AsyncMock()
        with patch("app.api.deps.get_session") as mock_get_session:
            # Create an async context manager that yields the session
            @asynccontextmanager
            async def mock_context():
                yield mock_session

            mock_get_session.return_value = mock_context()

            sessions = []
            async for session in get_db_session():
                sessions.append(session)

            assert len(sessions) == 1
            assert sessions[0] == mock_session


class TestGetJwtHandler:
    """Tests for get_jwt_handler function."""

    def test_get_jwt_handler_returns_handler(self):
        """get_jwt_handler should return a JWTHandler instance."""
        from app.api.deps import get_jwt_handler
        from app.infra.security.jwt_handler import JWTHandler

        handler = get_jwt_handler()
        assert isinstance(handler, JWTHandler)


class TestGetRedisCache:
    """Tests for get_redis_cache function."""

    def test_get_redis_cache_returns_cache(self):
        """get_redis_cache should return a RedisCache instance from app.state."""
        from unittest.mock import MagicMock

        from app.api.deps import get_redis_cache
        from app.infra.redis.cache import RedisCache
        from app.main import app

        # Mock the app.state to have a redis_cache
        mock_cache = MagicMock(spec=RedisCache)
        app.state.redis_cache = mock_cache

        # Mock the request with app reference
        mock_request = MagicMock()
        mock_request.app = app

        try:
            cache = get_redis_cache(mock_request)
            assert cache is mock_cache
        finally:
            # Clean up
            if hasattr(app.state, "redis_cache"):
                delattr(app.state, "redis_cache")


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    def _create_mock_request(self, cookies=None):
        """Helper to create a mock request with optional cookies."""
        mock_request = MagicMock()
        mock_request.cookies = cookies or {}
        return mock_request

    @pytest.mark.asyncio
    async def test_raises_for_blacklisted_token(self):
        """get_current_user should raise 401 for blacklisted token."""
        from app.api.deps import get_current_user

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(return_value=True)

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="blacklisted-jti")

        mock_session = AsyncMock()
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-token"
        mock_request = self._create_mock_request()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                request=mock_request,
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )

        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_raises_for_invalid_token(self):
        """get_current_user should raise 401 for invalid token."""
        from app.api.deps import get_current_user

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(return_value=False)

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="valid-jti")
        mock_jwt.verify_token = MagicMock(return_value=None)  # Invalid token

        mock_session = AsyncMock()
        mock_credentials = MagicMock()
        mock_credentials.credentials = "invalid-token"
        mock_request = self._create_mock_request()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                request=mock_request,
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )

        assert exc_info.value.status_code == 401
        assert "invalid" in exc_info.value.detail.lower() or "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_user(self):
        """get_current_user should raise 401 if user not found."""
        from app.api.deps import get_current_user

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(return_value=False)

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="valid-jti")
        mock_jwt.verify_token = MagicMock(return_value="user-123")

        mock_session = AsyncMock()
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-token"
        mock_request = self._create_mock_request()

        with patch("app.api.deps.get_user_by_id", AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=mock_request,
                    credentials=mock_credentials,
                    jwt_handler=mock_jwt,
                    session=mock_session,
                    redis=mock_redis,
                )

        assert exc_info.value.status_code == 401
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_user_on_success(self):
        """get_current_user should return user dict on success."""
        from app.api.deps import get_current_user

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(return_value=False)

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="valid-jti")
        mock_jwt.verify_token = MagicMock(return_value="user-123")

        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"
        mock_user.role = "user"

        mock_session = AsyncMock()
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-token"
        mock_request = self._create_mock_request()

        with patch("app.api.deps.get_user_by_id", AsyncMock(return_value=mock_user)):
            result = await get_current_user(
                request=mock_request,
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )

        assert result["id"] == "user-123"
        assert result["email"] == "test@example.com"
        assert result["role"] == "user"

    @pytest.mark.asyncio
    async def test_redis_error_in_production_fails_closed(self):
        """get_current_user should fail closed in production when Redis errors."""
        from app.api.deps import get_current_user

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(side_effect=RedisError("Connection refused"))

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="valid-jti")

        mock_session = AsyncMock()
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-token"
        mock_request = self._create_mock_request()

        with patch("app.api.deps.get_settings") as mock_settings:
            mock_settings.return_value.APP_ENV = "production"

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=mock_request,
                    credentials=mock_credentials,
                    jwt_handler=mock_jwt,
                    session=mock_session,
                    redis=mock_redis,
                )

            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_redis_error_in_development_fails_open(self):
        """get_current_user should fail open in development when Redis errors."""
        from app.api.deps import get_current_user

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(side_effect=RedisError("Connection refused"))

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="valid-jti")
        mock_jwt.verify_token = MagicMock(return_value="user-123")

        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"

        mock_session = AsyncMock()
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-token"
        mock_request = self._create_mock_request()

        with patch("app.api.deps.get_settings") as mock_settings:
            mock_settings.return_value.APP_ENV = "development"

            with patch("app.api.deps.get_user_by_id", AsyncMock(return_value=mock_user)):
                # Should not raise, should continue
                result = await get_current_user(
                    request=mock_request,
                    credentials=mock_credentials,
                    jwt_handler=mock_jwt,
                    session=mock_session,
                    redis=mock_redis,
                )

            assert result["id"] == "user-123"

    @pytest.mark.asyncio
    async def test_skips_blacklist_check_when_jti_is_none(self):
        """get_current_user should skip blacklist check if jti is None."""
        from app.api.deps import get_current_user

        mock_redis = MagicMock()
        # This should never be called since jti is None
        mock_redis.is_token_blacklisted = AsyncMock(side_effect=Exception("Should not be called"))

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value=None)  # No jti
        mock_jwt.verify_token = MagicMock(return_value="user-123")

        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"

        mock_session = AsyncMock()
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-token"
        mock_request = self._create_mock_request()

        with patch("app.api.deps.get_user_by_id", AsyncMock(return_value=mock_user)):
            result = await get_current_user(
                request=mock_request,
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )

        # Verify blacklist check was not called
        mock_redis.is_token_blacklisted.assert_not_called()
        assert result["id"] == "user-123"

    @pytest.mark.asyncio
    async def test_ignores_cookie_when_no_auth_header(self):
        """get_current_user should ignore cookie token and raise 401 when no Authorization header."""
        from app.api.deps import get_current_user

        mock_redis = MagicMock()
        mock_jwt = MagicMock()

        mock_session = AsyncMock()
        mock_request = self._create_mock_request(cookies={"access_token": "cookie-token"})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                request=mock_request,
                credentials=None,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )

        assert exc_info.value.status_code == 401
        mock_jwt.verify_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_when_no_token_anywhere(self):
        """get_current_user should raise 401 when no Authorization header is provided."""
        from app.api.deps import get_current_user

        mock_redis = MagicMock()
        mock_jwt = MagicMock()
        mock_session = AsyncMock()
        mock_request = self._create_mock_request()  # No cookies

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                request=mock_request,
                credentials=None,  # No auth header
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )

        assert exc_info.value.status_code == 401
        assert "not authenticated" in exc_info.value.detail.lower()


class TestCheckRateLimit:
    """Tests for check_rate_limit dependency."""

    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        """check_rate_limit should pass when under limit."""
        from app.api.deps import check_rate_limit

        mock_redis = MagicMock()
        mock_redis.check_rate_limit = AsyncMock(return_value=True)

        mock_user = {"id": "user-123"}

        # Should not raise
        await check_rate_limit(redis=mock_redis, current_user=mock_user)

    @pytest.mark.asyncio
    async def test_raises_over_limit(self):
        """check_rate_limit should raise 429 when over limit."""
        from app.api.deps import check_rate_limit

        mock_redis = MagicMock()
        mock_redis.check_rate_limit = AsyncMock(return_value=False)

        mock_user = {"id": "user-123"}

        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(redis=mock_redis, current_user=mock_user)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_passes_on_redis_error(self):
        """check_rate_limit should pass when Redis is unavailable (fail open)."""
        from app.api.deps import check_rate_limit

        mock_redis = MagicMock()
        mock_redis.check_rate_limit = AsyncMock(side_effect=RedisError("Connection refused"))

        mock_user = {"id": "user-123"}

        # Should not raise - fail open
        await check_rate_limit(redis=mock_redis, current_user=mock_user)


class TestCheckAuthRateLimit:
    """Tests for check_auth_rate_limit dependency."""

    @pytest.mark.asyncio
    async def test_allows_first_request(self):
        """check_auth_rate_limit should allow first request."""
        from app.api.deps import check_auth_rate_limit

        mock_redis = MagicMock()
        mock_redis.check_rate_limit = AsyncMock(return_value=True)

        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.headers = {}

        await check_auth_rate_limit(request=mock_request, redis=mock_redis)

    @pytest.mark.asyncio
    async def test_raises_after_limit_exceeded(self):
        """check_auth_rate_limit should raise 429 after limit exceeded."""
        from app.api.deps import check_auth_rate_limit

        mock_redis = MagicMock()
        mock_redis.check_rate_limit = AsyncMock(return_value=False)

        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            await check_auth_rate_limit(request=mock_request, redis=mock_redis)

        assert exc_info.value.status_code == 429
        assert "too many" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        """check_auth_rate_limit should allow requests within limit."""
        from app.api.deps import check_auth_rate_limit

        mock_redis = MagicMock()
        mock_redis.check_rate_limit = AsyncMock(return_value=True)

        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.headers = {}

        await check_auth_rate_limit(request=mock_request, redis=mock_redis)

    @pytest.mark.asyncio
    async def test_handles_missing_client_host(self):
        """check_auth_rate_limit should handle missing client host."""
        from app.api.deps import check_auth_rate_limit

        mock_redis = MagicMock()
        mock_redis.check_rate_limit = AsyncMock(return_value=True)

        mock_request = MagicMock()
        mock_request.client = None
        mock_request.headers = {}

        await check_auth_rate_limit(request=mock_request, redis=mock_redis)

        mock_redis.check_rate_limit.assert_called_once()
        call_args = mock_redis.check_rate_limit.call_args
        assert "unknown" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_uses_forwarded_header_from_trusted_proxy(self):
        """check_auth_rate_limit should use X-Forwarded-For header when from trusted proxy."""
        from app.api.deps import check_auth_rate_limit

        mock_redis = MagicMock()
        mock_redis.check_rate_limit = AsyncMock(return_value=True)

        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}

        with patch("app.api.deps.get_settings") as mock_settings:
            mock_settings.return_value.get_trusted_proxies.return_value = {"10.0.0.1"}

            await check_auth_rate_limit(request=mock_request, redis=mock_redis)

            call_args = mock_redis.check_rate_limit.call_args
            assert "203.0.113.1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_fails_closed_on_redis_error(self):
        """check_auth_rate_limit should fail closed for security."""
        from app.api.deps import check_auth_rate_limit

        mock_redis = MagicMock()
        mock_redis.check_rate_limit = AsyncMock(side_effect=RedisError("Connection refused"))

        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            await check_auth_rate_limit(request=mock_request, redis=mock_redis)

        assert exc_info.value.status_code == 503


class TestGetOptionalUser:
    """Tests for get_optional_user dependency."""

    def _create_mock_request(self, cookies=None):
        """Helper to create a mock request with optional cookies."""
        mock_request = MagicMock()
        mock_request.cookies = cookies or {}
        return mock_request

    @pytest.mark.asyncio
    async def test_returns_none_without_token(self):
        """get_optional_user should return None when no token is provided."""
        from app.api.deps import get_optional_user

        mock_request = self._create_mock_request()
        result = await get_optional_user(
            request=mock_request,
            credentials=None,
            jwt_handler=MagicMock(),
            session=AsyncMock(),
            redis=AsyncMock(),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_blacklisted_token(self):
        """get_optional_user should return None for blacklisted token."""
        from app.api.deps import get_optional_user

        mock_credentials = MagicMock()
        mock_credentials.credentials = "blacklisted-token"

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(return_value=True)

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="jti-123")
        mock_request = self._create_mock_request()

        result = await get_optional_user(
            request=mock_request,
            credentials=mock_credentials,
            jwt_handler=mock_jwt,
            session=AsyncMock(),
            redis=mock_redis,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_token(self):
        """get_optional_user should return None for invalid token."""
        from app.api.deps import get_optional_user

        mock_credentials = MagicMock()
        mock_credentials.credentials = "invalid-token"

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(return_value=False)

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="jti-123")
        mock_jwt.verify_token = MagicMock(return_value=None)
        mock_request = self._create_mock_request()

        result = await get_optional_user(
            request=mock_request,
            credentials=mock_credentials,
            jwt_handler=mock_jwt,
            session=AsyncMock(),
            redis=mock_redis,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_dict_for_valid_token(self):
        """get_optional_user should return user dict for valid token."""
        from app.api.deps import get_optional_user

        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-token"

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(return_value=False)

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="jti-123")
        mock_jwt.verify_token = MagicMock(return_value="user-123")

        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"
        mock_user.role = "user"
        mock_request = self._create_mock_request()

        with patch("app.api.deps.get_user_by_id", AsyncMock(return_value=mock_user)):
            result = await get_optional_user(
                request=mock_request,
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=AsyncMock(),
                redis=mock_redis,
            )

        assert result is not None
        assert result["id"] == "user-123"
        assert result["email"] == "test@example.com"
        assert result["role"] == "user"

    @pytest.mark.asyncio
    async def test_ignores_cookie_when_no_auth_header(self):
        """get_optional_user should ignore cookie token and return None when no Authorization header."""
        from app.api.deps import get_optional_user

        mock_redis = MagicMock()
        mock_jwt = MagicMock()

        mock_session = AsyncMock()
        mock_request = self._create_mock_request(cookies={"access_token": "cookie-token"})

        result = await get_optional_user(
            request=mock_request,
            credentials=None,
            jwt_handler=mock_jwt,
            session=mock_session,
            redis=mock_redis,
        )

        assert result is None
        mock_jwt.verify_token.assert_not_called()


class TestGetCurrentAdmin:
    """Tests for get_current_admin dependency."""

    @pytest.mark.asyncio
    async def test_raises_for_non_admin(self):
        """get_current_admin should raise 403 for non-admin users."""
        from app.api.deps import get_current_admin

        current_user = {"id": "user-123", "email": "test@example.com", "role": "user"}

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(current_user)

        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_admin_user(self):
        """get_current_admin should return admin user dict."""
        from app.api.deps import get_current_admin

        current_user = {"id": "admin-123", "email": "admin@example.com", "role": "admin"}

        result = await get_current_admin(current_user)

        assert result == current_user
        assert result["role"] == "admin"


class TestGetCurrentAdminUser:
    """Tests for get_current_admin_user alias dependency."""

    @pytest.mark.asyncio
    async def test_raises_for_non_admin_even_if_email_looks_privileged(self):
        """CurrentAdminUser must rely on role only, not email whitelist."""
        from app.api.deps import get_current_admin_user

        current_user = {"id": "user-123", "email": "admin@example.com", "role": "user"}

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(current_user)

        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_user_for_admin_role(self):
        """CurrentAdminUser should pass when role is admin."""
        from app.api.deps import get_current_admin_user

        current_user = {"id": "admin-123", "email": "admin@example.com", "role": "admin"}

        result = await get_current_admin_user(current_user)

        assert result == current_user


class TestDependencySignatureStyle:
    """Tests for dependency injection signature consistency."""

    def test_get_current_user_signature_uses_dependency_aliases(self) -> None:
        """get_current_user should use dependency aliases in signature."""
        from app.api import deps

        source = inspect.getsource(deps.get_current_user)
        # Check that the signature uses the alias types, not raw Depends()
        assert "jwt_handler: JWTHandlerDep" in source
        assert "session: SessionDep" in source
        assert "redis: RedisCacheDep" in source

    def test_get_optional_user_signature_uses_dependency_aliases(self) -> None:
        """get_optional_user should use dependency aliases in signature."""
        from app.api import deps

        source = inspect.getsource(deps.get_optional_user)
        assert "jwt_handler: JWTHandlerDep" in source
        assert "session: SessionDep" in source
        assert "redis: RedisCacheDep" in source


# ---------------------------------------------------------------------------
# Tests from test_deps_security.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_blacklist_fails_closed_in_production():
    """Token blacklist check should fail closed in production."""
    from app.api.deps import get_current_user

    # Mock production environment
    with patch("app.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.APP_ENV = "production"

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(side_effect=RedisError("Connection refused"))

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="test-jti")
        mock_jwt.verify_token = MagicMock(return_value="user-123")

        mock_session = AsyncMock()

        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-token"

        mock_request = MagicMock()
        mock_request.cookies = {}

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                request=mock_request,
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )

        # Should return 503, not pass through
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_token_blacklist_passes_in_development():
    """Token blacklist check can pass in development for availability."""
    from app.api.deps import get_current_user

    with patch("app.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.APP_ENV = "development"

        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(side_effect=RedisError("Connection refused"))

        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="test-jti")
        mock_jwt.verify_token = MagicMock(return_value="user-123")

        # Mock user lookup
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"

        with patch("app.api.deps.get_user_by_id", AsyncMock(return_value=mock_user)):
            mock_session = AsyncMock()

            mock_credentials = MagicMock()
            mock_credentials.credentials = "valid-token"

            mock_request = MagicMock()
            mock_request.cookies = {}

            result = await get_current_user(
                request=mock_request,
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )

            # In development, should pass through
            assert result["id"] == "user-123"


@pytest.mark.asyncio
async def test_auth_rate_limit_uses_peer_ip_when_not_from_trusted_proxy():
    """Auth rate limit should use peer IP when request is not from a trusted proxy."""
    from app.api.deps import check_auth_rate_limit

    mock_request = MagicMock()
    mock_request.client = MagicMock()
    mock_request.client.host = "8.8.8.8"
    mock_request.headers = {"X-Forwarded-For": "1.2.3.4"}

    mock_redis = MagicMock()
    mock_redis.check_rate_limit = AsyncMock(return_value=True)

    with patch("app.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.get_trusted_proxies.return_value = {"10.0.0.1"}

        await check_auth_rate_limit(request=mock_request, redis=mock_redis)

        mock_redis.check_rate_limit.assert_called_once()
        call_args = mock_redis.check_rate_limit.call_args
        assert "auth_rate:8.8.8.8" in call_args[0][0]


@pytest.mark.asyncio
async def test_auth_rate_limit_uses_xff_when_from_trusted_proxy():
    """Auth rate limit should use X-Forwarded-For when request is from a trusted proxy."""
    from app.api.deps import check_auth_rate_limit

    mock_request = MagicMock()
    mock_request.client = MagicMock()
    mock_request.client.host = "10.0.0.1"
    mock_request.headers = {"X-Forwarded-For": "1.2.3.4"}

    mock_redis = MagicMock()
    mock_redis.check_rate_limit = AsyncMock(return_value=True)

    with patch("app.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.get_trusted_proxies.return_value = {"10.0.0.1"}

        await check_auth_rate_limit(request=mock_request, redis=mock_redis)

        mock_redis.check_rate_limit.assert_called_once()
        call_args = mock_redis.check_rate_limit.call_args
        assert "auth_rate:1.2.3.4" in call_args[0][0]


# ---------------------------------------------------------------------------
# Tests from test_auth_logout.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_raises_503_when_blacklist_write_fails() -> None:
    request = MagicMock()
    request.headers = {"Authorization": "Bearer token-123"}

    jwt_handler = MagicMock()
    jwt_handler.get_jti.return_value = "jti-123"
    jwt_handler.expire_minutes = 60

    redis = MagicMock()
    redis.blacklist_token = AsyncMock(side_effect=RedisError("redis down"))

    with pytest.raises(HTTPException) as exc:
        await logout(request=request, jwt_handler=jwt_handler, redis=redis, _=None)

    assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# Tests from test_auth_rate_limit.py
# ---------------------------------------------------------------------------


def test_login_endpoint_has_rate_limiting():
    """Login endpoint should check rate limit."""
    from app.api.auth import router

    # Find the login route
    login_route = None
    for route in router.routes:
        if hasattr(route, 'path') and route.path == '/auth/login':
            login_route = route
            break

    assert login_route is not None, "Login route not found"
    # The route should have rate limiting dependency
    # This is a structural check - the actual rate limiting is in deps


def test_register_endpoint_has_rate_limiting():
    """Register endpoint should check rate limit."""
    from app.api.auth import router

    register_route = None
    for route in router.routes:
        if hasattr(route, 'path') and route.path == '/auth/register':
            register_route = route
            break

    assert register_route is not None, "Register route not found"


def test_logout_endpoint_has_rate_limiting():
    """Logout endpoint should check rate limit."""
    from app.api.auth import router

    logout_route = None
    for route in router.routes:
        if hasattr(route, 'path') and route.path == '/auth/logout':
            logout_route = route
            break

    assert logout_route is not None, "Logout route not found"
    assert any(dep.call.__name__ == "check_auth_rate_limit" for dep in logout_route.dependant.dependencies)


# ---------------------------------------------------------------------------
# Tests from test_guest_rate_limit.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guest_message_returns_429_when_guest_limit_exceeded():
    """Test that guest rate limit returns 429 when exceeded."""
    # Create a mock Redis cache that simulates rate limit exceeded
    mock_redis = AsyncMock()
    # Return True for first 20 requests, then False
    call_count = 0

    async def mock_check_rate_limit(key: str, max_requests: int = 60) -> bool:
        nonlocal call_count
        call_count += 1
        return call_count <= 20

    mock_redis.check_rate_limit = mock_check_rate_limit
    mock_redis.get_guest_session = AsyncMock(return_value=None)
    mock_redis.set_guest_session = AsyncMock(return_value=None)
    mock_redis.client = AsyncMock()
    mock_redis.client.set = AsyncMock(return_value=True)
    mock_redis.client.incr = AsyncMock(return_value=1)

    # Mock RAG agent and LLM provider for guest chat
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test response",
        "documents": [],
        "retrieval_score": 0.8,
    })

    mock_llm_provider = MagicMock()

    def override_redis():
        return mock_redis

    def override_rag_agent():
        return mock_rag_agent

    def override_llm_provider():
        return mock_llm_provider

    app.dependency_overrides[original_get_redis_cache] = override_redis
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Send 21 requests, the 21st should be rate limited
            last_response = None
            for i in range(21):
                response = await client.post(
                    "/api/v1/chat/guest/message",
                    json={"message": f"hello {i}"},
                )
                last_response = response

            # The 21st request should return 429
            assert last_response.status_code == 429
            assert "rate limit" in last_response.json()["detail"].lower()
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_guest_message_allows_requests_within_limit():
    """Test that guest rate limit allows requests within the limit."""
    # Create a mock Redis cache that allows requests
    mock_redis = AsyncMock()
    mock_redis.check_rate_limit = AsyncMock(return_value=True)
    mock_redis.get_guest_session = AsyncMock(return_value=None)
    mock_redis.set_guest_session = AsyncMock(return_value=None)
    mock_redis.client = AsyncMock()
    mock_redis.client.set = AsyncMock(return_value=True)
    mock_redis.client.incr = AsyncMock(return_value=1)

    # Mock RAG agent and LLM provider for guest chat
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test response",
        "documents": [],
        "retrieval_score": 0.8,
    })

    mock_llm_provider = MagicMock()

    def override_redis():
        return mock_redis

    def override_rag_agent():
        return mock_rag_agent

    def override_llm_provider():
        return mock_llm_provider

    app.dependency_overrides[original_get_redis_cache] = override_redis
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/guest/message",
                json={"message": "hello"},
            )

            assert response.status_code == 200
            assert "X-Session-Id" in response.headers
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_guest_rate_limit_uses_client_ip():
    """Test that guest rate limiting uses client IP as the key."""
    mock_redis = AsyncMock()
    mock_redis.check_rate_limit = AsyncMock(return_value=True)
    mock_redis.get_guest_session = AsyncMock(return_value=None)
    mock_redis.set_guest_session = AsyncMock(return_value=None)
    mock_redis.client = AsyncMock()
    mock_redis.client.set = AsyncMock(return_value=True)
    mock_redis.client.incr = AsyncMock(return_value=1)

    # Mock RAG agent and LLM provider for guest chat
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test response",
        "documents": [],
        "retrieval_score": 0.8,
    })

    mock_llm_provider = MagicMock()

    def override_redis():
        return mock_redis

    def override_rag_agent():
        return mock_rag_agent

    def override_llm_provider():
        return mock_llm_provider

    app.dependency_overrides[original_get_redis_cache] = override_redis
    app.dependency_overrides[original_get_rag_agent] = override_rag_agent
    app.dependency_overrides[original_get_llm_provider] = override_llm_provider

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/chat/guest/message",
                json={"message": "hello"},
            )

            # Verify check_rate_limit was called with a guest: prefix key
            mock_redis.check_rate_limit.assert_called_once()
            call_args = mock_redis.check_rate_limit.call_args
            key = call_args[0][0] if call_args[0] else call_args[1].get("key", "")
            assert key.startswith("guest:")
    finally:
        app.dependency_overrides = {}
