# backend/tests/unit/test_password.py
from app.infra.security.password import hash_password, verify_password


def test_hash_password():
    password = "secure_password_123"
    hashed = hash_password(password)

    assert hashed != password
    assert len(hashed) > 0
    assert hashed.startswith("v1:$2b$")


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


def test_long_passwords_differing_only_after_72_bytes_produce_DIFFERENT_hashes():
    a = "A" * 72 + "suffix_a"
    b = "A" * 72 + "suffix_b"
    hash_a = hash_password(a)
    assert verify_password(a, hash_a) is True
    assert verify_password(b, hash_a) is False, (
        "72-byte truncation regression: `b` verifies against `a`'s hash. "
        "hash_password must pre-hash long inputs."
    )


def test_hash_password_produces_v1_prefixed_output():
    result = hash_password("SomeStrong!Password42")
    assert result.startswith("v1:"), (
        f"Expected 'v1:'-prefixed hash, got {result[:10]!r}"
    )
    assert result[3:].startswith("$2b$")


def test_verify_password_accepts_v1_prefixed_hash():
    password = "SomeStrong!Password42"
    stored = hash_password(password)
    assert verify_password(password, stored) is True
    assert verify_password("wrong", stored) is False


def test_verify_password_accepts_legacy_unprefixed_bcrypt_hash():
    import bcrypt as _bcrypt
    password = "LegacyUser!Password"
    legacy_hash = _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    assert not legacy_hash.startswith("v1:")

    assert verify_password(password, legacy_hash) is True
    assert verify_password("wrong", legacy_hash) is False


def test_verify_password_rejects_malformed_hash_without_crashing():
    assert verify_password("anything", "not-a-real-hash") is False
    assert verify_password("anything", "") is False
    assert verify_password("anything", "v1:notbcrypt") is False
