# backend/tests/unit/test_deps_security.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
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

            result = await get_current_user(
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )

            # In development, should pass through
            assert result["id"] == "user-123"
