from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth_service import get_user_by_id
from app.config.settings import get_settings
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.redis.cache import RedisCache
from app.infra.security.jwt_handler import JWTHandler

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
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    jwt_handler: JWTHandler = Depends(get_jwt_handler),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
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


async def check_rate_limit(
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> None:
    """Check rate limit for the current user.

    Fails open if Redis is unavailable to ensure availability during outages.
    """
    try:
        if not await redis.check_rate_limit(current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
    except RedisError:
        # Log the error but allow request to proceed
        # This ensures availability during Redis outages
        pass


RateLimitDep = Annotated[None, Depends(check_rate_limit)]


async def check_auth_rate_limit(
    request: Request,
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
) -> None:
    """Rate limiting for authentication endpoints using IP address.

    More restrictive than regular rate limiting:
    - 5 requests per minute for login
    - 3 requests per minute for register

    Fails closed for security - returns 503 if Redis unavailable.
    """
    # Get client IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    key = f"auth_rate:{client_ip}"

    try:
        first_request = await redis.client.set(key, 1, ex=60, nx=True)
        if first_request:
            return

        count = await redis.client.incr(key)
        if count > 5:  # 5 attempts per minute
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication attempts. Please try again later.",
            )
    except RedisError as e:
        # Fail closed for auth endpoints - security over availability
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication temporarily unavailable. Please try again later.",
        ) from e


AuthRateLimitDep = Annotated[None, Depends(check_auth_rate_limit)]
