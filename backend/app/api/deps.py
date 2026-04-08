from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth_service import get_user_by_id
from app.config.settings import get_settings
from app.infra.cache.prompt_cache import PromptCache
from app.infra.postgres.database import get_session
from app.infra.redis.cache import RedisCache
from app.infra.security.jwt_handler import JWTHandler

security = HTTPBearer()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session from the global session maker."""
    async with get_session() as session:
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


def get_redis_cache(request: Request) -> RedisCache:
    """Get Redis cache from app.state singleton via Request."""
    if hasattr(request.app.state, "redis_cache"):
        return request.app.state.redis_cache
    raise RuntimeError("Redis cache not initialized. App not started?")


RedisCacheDep = Annotated[RedisCache, Depends(get_redis_cache)]


def get_prompt_cache(request: Request) -> PromptCache:
    """Get PromptCache from app.state singleton via Request."""
    if hasattr(request.app.state, "prompt_cache"):
        return request.app.state.prompt_cache
    raise RuntimeError("Prompt cache not initialized. App not started?")


PromptCacheDep = Annotated[PromptCache, Depends(get_prompt_cache)]


async def get_current_user(
    jwt_handler: JWTHandlerDep,
    session: SessionDep,
    redis: RedisCacheDep,
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
) -> dict:
    token = credentials.credentials

    # Check if token is blacklisted
    jti = jwt_handler.get_jti(token)
    if jti:
        try:
            if await redis.is_token_blacklisted(jti):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except RedisError as e:
            # In production, fail closed for security
            # In development, fail open for availability
            settings = get_settings()
            if settings.APP_ENV == "production":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication temporarily unavailable",
                ) from e
            # In development, log and continue
            logger.warning(f"Redis error during blacklist check: {e}")

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

    return {"id": user.id, "email": user.email, "role": user.role}


CurrentUser = Annotated[dict, Depends(get_current_user)]


async def get_optional_user(
    jwt_handler: JWTHandlerDep,
    session: SessionDep,
    redis: RedisCacheDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),  # noqa: B008
) -> dict | None:
    """Get current user if authenticated, else return None (for guest access)."""
    if credentials is None:
        return None

    token = credentials.credentials

    # Check if token is blacklisted
    jti = jwt_handler.get_jti(token)
    if jti:
        try:
            if await redis.is_token_blacklisted(jti):
                return None
        except RedisError:
            # In development, continue without blacklist check
            pass

    user_id = jwt_handler.verify_token(token)
    if user_id is None:
        return None

    user = await get_user_by_id(session, user_id)
    if user is None:
        return None

    return {"id": user.id, "email": user.email, "role": user.role}


OptionalUser = Annotated[dict | None, Depends(get_optional_user)]


async def get_current_admin(
    current_user: CurrentUser,
) -> dict:
    """Require admin role for endpoint access."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


CurrentAdmin = Annotated[dict, Depends(get_current_admin)]


async def get_current_admin_user(
    current_user: CurrentUser,
) -> dict:
    """Require admin role for endpoint access (alias for get_current_admin).

    Checks if the user's email is in the ADMIN_EMAILS setting or if their role is 'admin'.
    """
    from app.config.settings import get_settings

    settings = get_settings()
    admin_emails = settings.get_admin_emails()

    # Check if user is admin by role or by email
    is_admin = current_user.get("role") == "admin" or current_user.get("email") in admin_emails

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


CurrentAdminUser = Annotated[dict, Depends(get_current_admin_user)]


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
    - 5 requests per minute for login and register

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
