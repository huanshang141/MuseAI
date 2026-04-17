import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt


class JWTHandler:
    def __init__(self, secret: str, algorithm: str, expire_minutes: int):
        self.secret = secret
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes

    def create_token(self, user_id: str, extra_data: dict[str, Any] | None = None) -> str:
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=self.expire_minutes)

        payload = dict(extra_data) if extra_data else {}
        payload.update({
            "sub": user_id,
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "access",
        })

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify_token(self, token: str) -> str | None:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except JWTError:
            return None
        if payload.get("type") != "access":
            return None
        return payload.get("sub")

    def decode_token(self, token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except JWTError:
            return None

    def get_jti(self, token: str) -> str | None:
        payload = self.decode_token(token)
        return payload.get("jti") if payload else None
