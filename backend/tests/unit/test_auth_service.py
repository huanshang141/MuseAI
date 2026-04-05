# backend/tests/unit/test_auth_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError
from app.application.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    verify_token,
    get_user_by_id,
)
from app.api.auth import RegisterRequest


@pytest.mark.asyncio
async def test_register_user():
    """Test successful user registration."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    user = await register_user(
        session=mock_session,
        email="test@example.com",
        password="password123",
        hash_password_func=mock_hash_func,
    )

    assert user is not None
    assert user.email == "test@example.com"
    assert user.password_hash == "hashed_password_123"
    mock_hash_func.assert_called_once_with("password123")


@pytest.mark.asyncio
async def test_register_user_duplicate_email():
    """Test that registering with a duplicate email raises an integrity error."""
    from sqlalchemy.exc import IntegrityError

    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock(
        side_effect=IntegrityError("duplicate key", {}, None)
    )
    mock_session.refresh = AsyncMock()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    with pytest.raises(IntegrityError):
        await register_user(
            session=mock_session,
            email="duplicate@example.com",
            password="password123",
            hash_password_func=mock_hash_func,
        )


@pytest.mark.asyncio
async def test_authenticate_user_success():
    """Test successful user authentication with correct password."""
    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.email = "test@example.com"
    mock_user.password_hash = "hashed_password_123"

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result

    mock_verify = MagicMock(return_value=True)

    user = await authenticate_user(
        session=mock_session,
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

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result

    mock_verify = MagicMock(return_value=False)

    user = await authenticate_user(
        session=mock_session,
        email="test@example.com",
        password="wrong_password",
        verify_password_func=mock_verify,
    )

    assert user is None
    mock_verify.assert_called_once_with("wrong_password", "hashed_password_123")


@pytest.mark.asyncio
async def test_authenticate_user_not_found():
    """Test authentication failure when user is not found."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    mock_verify = MagicMock(return_value=True)

    user = await authenticate_user(
        session=mock_session,
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

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result

    user = await get_user_by_id(session=mock_session, user_id="user-123")

    assert user is not None
    assert user.id == "user-123"
    assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_get_user_by_id_not_found():
    """Test retrieving a user by ID when user does not exist."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    user = await get_user_by_id(session=mock_session, user_id="nonexistent-user")

    assert user is None


# Password validation tests
def test_password_too_short():
    """Test that passwords shorter than 8 characters are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        RegisterRequest(email="test@example.com", password="Short1")
    assert "Password must be at least 8 characters" in str(exc_info.value)


def test_password_no_uppercase():
    """Test that passwords without uppercase letters are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        RegisterRequest(email="test@example.com", password="lowercase1")
    assert "Password must contain at least one uppercase letter" in str(exc_info.value)


def test_password_no_lowercase():
    """Test that passwords without lowercase letters are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        RegisterRequest(email="test@example.com", password="UPPERCASE1")
    assert "Password must contain at least one lowercase letter" in str(exc_info.value)


def test_password_no_digit():
    """Test that passwords without digits are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        RegisterRequest(email="test@example.com", password="NoDigitsHere")
    assert "Password must contain at least one digit" in str(exc_info.value)


def test_valid_password_accepted():
    """Test that valid passwords meeting all requirements are accepted."""
    request = RegisterRequest(email="test@example.com", password="ValidPass1")
    assert request.password == "ValidPass1"
    assert request.email == "test@example.com"


def test_valid_password_complex():
    """Test that complex valid passwords are accepted."""
    request = RegisterRequest(email="test@example.com", password="MySecure123Password")
    assert request.password == "MySecure123Password"


def test_password_validation_error_messages_clear():
    """Test that validation error messages are user-friendly."""
    with pytest.raises(ValidationError) as exc_info:
        RegisterRequest(email="test@example.com", password="weak")

    error_str = str(exc_info.value)
    # Should contain clear, user-friendly messages
    assert "Password must be at least 8 characters" in error_str
