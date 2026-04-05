from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt


class JWTHandler:
    def __init__(self, secret: str, algorithm: str, expire_minutes: int):
        self.secret = secret
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes

    def create_token(self, user_id: str, extra_data: dict[str, Any] | None = None) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.expire_minutes)

        payload = dict(extra_data) if extra_data else {}
        payload.update({
            "sub": user_id,
            "exp": expire,
            "iat": now,
        })

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify_token(self, token: str) -> str | None:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload.get("sub")
        except JWTError:
            return None

    def decode_token(self, token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except JWTError:
            return None
