# backend/tests/unit/test_auth_service.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.auth import RegisterRequest
from app.application.auth_service import (
    authenticate_user,
    create_access_token,
    get_user_by_id,
    register_user,
    verify_token,
)
from pydantic import ValidationError


def create_mock_user_repo():
    """Create a mock user repository for testing."""
    mock_repo = MagicMock()
    mock_repo.add = AsyncMock()
    mock_repo.get_by_email = AsyncMock(return_value=None)
    mock_repo.get_by_id = AsyncMock(return_value=None)
    return mock_repo


@pytest.mark.asyncio
async def test_register_user():
    """Test successful user registration."""
    mock_repo = create_mock_user_repo()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    user = await register_user(
        user_repo=mock_repo,
        email="test@example.com",
        password="password123",
        hash_password_func=mock_hash_func,
    )

    assert user is not None
    assert user.email == "test@example.com"
    assert user.password_hash == "hashed_password_123"
    mock_hash_func.assert_called_once_with("password123")
    mock_repo.add.assert_called_once()


@pytest.mark.asyncio
async def test_register_user_duplicate_email():
    """Test that registering with a duplicate email raises an integrity error."""
    from sqlalchemy.exc import IntegrityError

    mock_repo = create_mock_user_repo()
    mock_repo.add = AsyncMock(side_effect=IntegrityError("duplicate key", {}, None))

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    with pytest.raises(IntegrityError):
        await register_user(
            user_repo=mock_repo,
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
    request = RegisterRequest(email="test@example.com", password="ValidPass1!")
    assert request.password == "ValidPass1!"
    assert request.email == "test@example.com"


def test_valid_password_complex():
    """Test that complex valid passwords are accepted."""
    request = RegisterRequest(email="test@example.com", password="MySecure123Password!")
    assert request.password == "MySecure123Password!"


def test_password_validation_error_messages_clear():
    """Test that validation error messages are user-friendly."""
    with pytest.raises(ValidationError) as exc_info:
        RegisterRequest(email="test@example.com", password="weak")

    error_str = str(exc_info.value)
    # Should contain clear, user-friendly messages
    assert "Password must be at least 8 characters" in error_str


# Role assignment tests
@pytest.mark.asyncio
async def test_register_user_assigns_admin_role():
    """Test that user gets admin role when email is in admin_emails list."""
    mock_repo = create_mock_user_repo()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    user = await register_user(
        user_repo=mock_repo,
        email="admin@example.com",
        password="password123",
        hash_password_func=mock_hash_func,
        admin_emails=["admin@example.com", "superadmin@example.com"],
    )

    assert user is not None
    assert user.email == "admin@example.com"
    assert user.role == "admin"
    mock_hash_func.assert_called_once_with("password123")


@pytest.mark.asyncio
async def test_register_user_assigns_user_role_when_not_in_admin_list():
    """Test that user gets user role when email is not in admin_emails list."""
    mock_repo = create_mock_user_repo()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    user = await register_user(
        user_repo=mock_repo,
        email="regular@example.com",
        password="password123",
        hash_password_func=mock_hash_func,
        admin_emails=["admin@example.com", "superadmin@example.com"],
    )

    assert user is not None
    assert user.email == "regular@example.com"
    assert user.role == "user"


@pytest.mark.asyncio
async def test_register_user_assigns_user_role_when_admin_emails_none():
    """Test that user gets user role when admin_emails is None."""
    mock_repo = create_mock_user_repo()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    user = await register_user(
        user_repo=mock_repo,
        email="regular@example.com",
        password="password123",
        hash_password_func=mock_hash_func,
        admin_emails=None,
    )

    assert user is not None
    assert user.email == "regular@example.com"
    assert user.role == "user"


@pytest.mark.asyncio
async def test_register_user_assigns_user_role_when_admin_emails_empty():
    """Test that user gets user role when admin_emails is empty list."""
    mock_repo = create_mock_user_repo()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    user = await register_user(
        user_repo=mock_repo,
        email="regular@example.com",
        password="password123",
        hash_password_func=mock_hash_func,
        admin_emails=[],
    )

    assert user is not None
    assert user.email == "regular@example.com"
    assert user.role == "user"


@pytest.mark.asyncio
async def test_register_user_role_case_sensitive_email():
    """Test that admin email matching is case-sensitive."""
    mock_repo = create_mock_user_repo()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    # Email with different case should not match
    user = await register_user(
        user_repo=mock_repo,
        email="Admin@Example.com",
        password="password123",
        hash_password_func=mock_hash_func,
        admin_emails=["admin@example.com"],
    )

    assert user is not None
    assert user.email == "Admin@Example.com"
    assert user.role == "user"