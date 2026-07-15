# backend/tests/unit/test_auth_service.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.auth_service import (
    authenticate_user,
    create_access_token,
    get_user_by_id,
    verify_token,
)


def create_mock_user_repo():
    """Create a mock user repository for testing."""
    mock_repo = MagicMock()
    mock_repo.add = AsyncMock()
    mock_repo.get_by_email = AsyncMock(return_value=None)
    mock_repo.get_by_id = AsyncMock(return_value=None)
    return mock_repo


@pytest.mark.asyncio
async def test_authenticate_user_success():
    """Test successful user authentication with correct password."""
    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.email = "test@example.com"
    mock_user.password_hash = "hashed_password_123"

    mock_repo = create_mock_user_repo()
    mock_repo.get_by_email = AsyncMock(return_value=mock_user)

    mock_verify = MagicMock(return_value=True)

    user = await authenticate_user(
        user_repo=mock_repo,
        email="test@example.com",
        password="password123",
        verify_password_func=mock_verify,
    )

    assert user is not None
    assert user.id == "user-123"
    mock_verify.assert_called_once_with("password123", "hashed_password_123")


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password():
    """Test authentication failure with wrong password."""
    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.password_hash = "hashed_password_123"

    mock_repo = create_mock_user_repo()
    mock_repo.get_by_email = AsyncMock(return_value=mock_user)

    mock_verify = MagicMock(return_value=False)

    user = await authenticate_user(
        user_repo=mock_repo,
        email="test@example.com",
        password="wrong_password",
        verify_password_func=mock_verify,
    )

    assert user is None
    mock_verify.assert_called_once_with("wrong_password", "hashed_password_123")


@pytest.mark.asyncio
async def test_authenticate_user_not_found():
    """Test authentication failure when user is not found."""
    mock_repo = create_mock_user_repo()

    mock_verify = MagicMock(return_value=True)

    user = await authenticate_user(
        user_repo=mock_repo,
        email="notfound@example.com",
        password="password123",
        verify_password_func=mock_verify,
    )

    assert user is None
    # Verify should not be called when user is not found
    mock_verify.assert_not_called()


def test_create_access_token():
    """Test access token creation."""
    mock_jwt_handler = MagicMock()
    mock_jwt_handler.create_token.return_value = "mock_token_123"

    token = create_access_token(user_id="user-123", jwt_handler=mock_jwt_handler)

    assert token == "mock_token_123"
    mock_jwt_handler.create_token.assert_called_once_with("user-123")


def test_verify_token_valid():
    """Test verifying a valid token."""
    mock_jwt_handler = MagicMock()
    mock_jwt_handler.verify_token.return_value = "user-123"

    result = verify_token(token="valid_token_123", jwt_handler=mock_jwt_handler)

    assert result == "user-123"
    mock_jwt_handler.verify_token.assert_called_once_with("valid_token_123")


def test_verify_token_invalid():
    """Test verifying an invalid token returns None."""
    mock_jwt_handler = MagicMock()
    mock_jwt_handler.verify_token.return_value = None

    result = verify_token(token="invalid_token", jwt_handler=mock_jwt_handler)

    assert result is None
    mock_jwt_handler.verify_token.assert_called_once_with("invalid_token")


@pytest.mark.asyncio
async def test_get_user_by_id_found():
    """Test retrieving a user by ID when user exists."""
    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.email = "test@example.com"

    mock_repo = create_mock_user_repo()
    mock_repo.get_by_id = AsyncMock(return_value=mock_user)

    user = await get_user_by_id(user_repo=mock_repo, user_id="user-123")

    assert user is not None
    assert user.id == "user-123"
    assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_get_user_by_id_not_found():
    """Test retrieving a user by ID when user does not exist."""
    mock_repo = create_mock_user_repo()

    user = await get_user_by_id(user_repo=mock_repo, user_id="nonexistent-user")

    assert user is None
