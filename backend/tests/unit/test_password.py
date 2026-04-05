# backend/tests/unit/test_password.py
from app.infra.security.password import hash_password, verify_password


def test_hash_password():
    password = "secure_password_123"
    hashed = hash_password(password)

    assert hashed != password
    assert len(hashed) > 0
    assert hashed.startswith("$2b$")


def test_verify_password_correct():
    password = "secure_password_123"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    password = "secure_password_123"
    wrong_password = "wrong_password"
    hashed = hash_password(password)

    assert verify_password(wrong_password, hashed) is False


def test_hash_password_different_each_time():
    password = "secure_password_123"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True
