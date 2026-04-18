"""Password hashing with SHA-256 pre-hash to avoid bcrypt's 72-byte truncation.

SEC-P2-03: bcrypt silently truncates input to 72 bytes. Pre-hashing with
SHA-256 + base64 encoding compresses any input to 44 ASCII bytes so every
byte of the user's password contributes to the final hash.

Backward compatibility: pre-SEC-P2-03 hashes carry no prefix. verify_password
dispatches on the 'v1:' prefix:
- 'v1:$2b$...' → SHA-256 pre-hash + bcrypt.checkpw
- '$2b$...'    → legacy direct bcrypt.checkpw (still correct for ≤72-byte passwords)

New hashes always carry the 'v1:' prefix. Users migrate naturally on next
password change.
"""
import base64
import hashlib

import bcrypt

_V1_PREFIX = "v1:"


def _prehash(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    bcrypt_hash = bcrypt.hashpw(_prehash(password), salt).decode("utf-8")
    return f"{_V1_PREFIX}{bcrypt_hash}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False

    try:
        if hashed_password.startswith(_V1_PREFIX):
            stored = hashed_password[len(_V1_PREFIX):]
            return bcrypt.checkpw(_prehash(plain_password), stored.encode("utf-8"))
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False
