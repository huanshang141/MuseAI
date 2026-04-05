# backend/tests/unit/test_auth_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.application.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
)


@pytest.mark.asyncio
async def test_register_user():
    mock_session = MagicMock()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    from app.infra.security import hash_password

    user = await register_user(
        session=mock_session,
        email="test@example.com",
        password="password123",
        hash_password_func=hash_password,
    )

    assert user is not None
    assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_authenticate_user_success():
    from app.infra.security import hash_password

    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.email = "test@example.com"
    mock_user.password_hash = hash_password("password123")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result

    user = await authenticate_user(
        session=mock_session,
        email="test@example.com",
        password="password123",
        verify_password_func=lambda p, h: p == "password123" and h == mock_user.password_hash,
    )

    assert user is not None
    assert user.id == "user-123"


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password():
    from app.infra.security import hash_password

    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.password_hash = hash_password("password123")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result

    user = await authenticate_user(
        session=mock_session,
        email="test@example.com",
        password="wrong_password",
        verify_password_func=lambda p, h: False,
    )

    assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    user = await authenticate_user(
        session=mock_session,
        email="notfound@example.com",
        password="password123",
        verify_password_func=lambda p, h: True,
    )

    assert user is None


def test_create_access_token():
    from app.infra.security.jwt_handler import JWTHandler

    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=60
    )

    token = create_access_token(user_id="user-123", jwt_handler=handler)

    assert token is not None
    assert isinstance(token, str)
