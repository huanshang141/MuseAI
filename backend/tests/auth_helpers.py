"""Test-only helpers for auth-protected route contracts.

Production has no registration route and only admins can obtain tokens through
the login API. Some authorization tests still need a signed non-admin token to
verify that admin dependencies return 403, so they mint it directly here.
"""

from __future__ import annotations

import uuid

from app.api.deps import get_jwt_handler
from app.infra.postgres.models import User
from app.infra.security.password import hash_password
from sqlalchemy import select


async def ensure_test_user(session, *, email: str, password: str, role: str) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"museai-test:{email}")),
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        session.add(user)
    else:
        user.password_hash = hash_password(password)
        user.role = role
    await session.commit()
    return user


def issue_test_token(user: User) -> str:
    return get_jwt_handler().create_token(user.id)
