from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.auth import logout
from fastapi import HTTPException
from redis.exceptions import RedisError


@pytest.mark.asyncio
async def test_logout_raises_503_when_blacklist_write_fails() -> None:
    request = MagicMock()
    request.headers = {"Authorization": "Bearer token-123"}

    jwt_handler = MagicMock()
    jwt_handler.get_jti.return_value = "jti-123"
    jwt_handler.expire_minutes = 60

    redis = MagicMock()
    redis.blacklist_token = AsyncMock(side_effect=RedisError("redis down"))

    response = MagicMock()

    with pytest.raises(HTTPException) as exc:
        await logout(request=request, jwt_handler=jwt_handler, redis=redis, response=response, _=None)

    assert exc.value.status_code == 503
