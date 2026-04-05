from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.security.jwt_handler import JWTHandler
from app.infra.redis.cache import RedisCache
from app.application.auth_service import get_user_by_id

security = HTTPBearer()

_session_maker = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    global _session_maker
    if _session_maker is None:
        settings = get_settings()
        _session_maker = get_session_maker(settings.DATABASE_URL)
    async with get_session(_session_maker) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_jwt_handler() -> JWTHandler:
    settings = get_settings()
    return JWTHandler(
        secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        expire_minutes=settings.JWT_EXPIRE_MINUTES,
    )


JWTHandlerDep = Annotated[JWTHandler, Depends(get_jwt_handler)]


def get_redis_cache() -> RedisCache:
    settings = get_settings()
    return RedisCache(settings.REDIS_URL)


RedisCacheDep = Annotated[RedisCache, Depends(get_redis_cache)]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    session: AsyncSession = Depends(get_db_session),
    redis: RedisCache = Depends(get_redis_cache),
) -> dict:
    token = credentials.credentials

    # Check if token is blacklisted (fail open if Redis is unavailable)
    jti = jwt_handler.get_jti(token)
    if jti:
        try:
            if await redis.is_token_blacklisted(jti):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except RedisError:
            # Log the error but allow request to proceed
            # This ensures availability during Redis outages
            pass

    user_id = jwt_handler.verify_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"id": user.id, "email": user.email}


CurrentUser = Annotated[dict, Depends(get_current_user)]
