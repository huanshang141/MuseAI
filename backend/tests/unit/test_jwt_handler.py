# backend/tests/unit/test_jwt_handler.py
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


def test_token_has_jti():
    """Test that created tokens have a jti (JWT ID) claim."""
    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)
    token = handler.create_token("user-123")

    payload = handler.decode_token(token)

    assert payload is not None
    assert "jti" in payload
    assert payload["jti"] is not None
    assert len(payload["jti"]) == 36  # UUID format


def test_get_jti():
    """Test extracting jti from a token."""
    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)
    token = handler.create_token("user-123")

    jti = handler.get_jti(token)

    assert jti is not None
    assert len(jti) == 36  # UUID format


def test_get_jti_invalid_token():
    """Test that get_jti returns None for invalid tokens."""
    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)

    jti = handler.get_jti("invalid-token")

    assert jti is None


def test_each_token_has_unique_jti():
    """Test that each created token has a unique jti."""
    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)

    token1 = handler.create_token("user-123")
    token2 = handler.create_token("user-123")

    jti1 = handler.get_jti(token1)
    jti2 = handler.get_jti(token2)

    assert jti1 != jti2


def test_verify_token_rejects_refresh_token():
    """A refresh token (type='refresh') must NOT be accepted by verify_token."""
    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)

    refresh_token = handler.create_refresh_token("user-123")

    user_id = handler.verify_token(refresh_token)

    assert user_id is None, (
        "verify_token must reject refresh tokens: got sub=%r" % user_id
    )


def test_verify_token_accepts_access_token_explicitly():
    """Sanity: a normal access token still passes verify_token."""
    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)
    access_token = handler.create_token("user-123")

    user_id = handler.verify_token(access_token)

    assert user_id == "user-123"
