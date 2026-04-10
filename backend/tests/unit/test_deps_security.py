# backend/tests/unit/test_deps_security.py

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError


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
