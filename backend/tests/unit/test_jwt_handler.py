# backend/tests/unit/test_jwt_handler.py
import pytest
from datetime import timedelta
from app.infra.security.jwt_handler import JWTHandler


def test_create_token():
    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=60
    )
    token = handler.create_token("user-123")

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_token_valid():
    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=60
    )
    token = handler.create_token("user-123")

    user_id = handler.verify_token(token)

    assert user_id == "user-123"


def test_verify_token_invalid():
    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=60
    )

    user_id = handler.verify_token("invalid-token")

    assert user_id is None


def test_verify_token_wrong_secret():
    handler1 = JWTHandler(
        secret="secret1",
        algorithm="HS256",
        expire_minutes=60
    )
    handler2 = JWTHandler(
        secret="secret2",
        algorithm="HS256",
        expire_minutes=60
    )

    token = handler1.create_token("user-123")
    user_id = handler2.verify_token(token)

    assert user_id is None


def test_decode_token():
    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=60
    )
    token = handler.create_token("user-123")

    payload = handler.decode_token(token)

    assert payload is not None
    assert payload.get("sub") == "user-123"
    assert "exp" in payload


def test_verify_token_expired():
    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=-1  # Already expired
    )
    token = handler.create_token("user-123")

    user_id = handler.verify_token(token)

    assert user_id is None


def test_create_token_with_extra_data():
    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)
    token = handler.create_token("user-123", extra_data={"role": "admin", "org": "acme"})

    payload = handler.decode_token(token)

    assert payload is not None
    assert payload.get("sub") == "user-123"
    assert payload.get("role") == "admin"
    assert payload.get("org") == "acme"
