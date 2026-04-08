from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.client_ip import extract_client_ip
from app.application.auth_service import get_user_by_id
from app.application.unified_indexing_service import UnifiedIndexingService
from app.config.settings import get_settings
from app.infra.cache.prompt_cache import PromptCache
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.postgres.adapters.auth_repository import PostgresUserRepository
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.redis.cache import RedisCache
from app.infra.security.jwt_handler import JWTHandler

security = HTTPBearer()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session from the global session maker."""
    async with get_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_db_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get the global session maker for creating short-lived sessions."""
    return get_session_maker()


SessionMakerDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_db_session_maker)]


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
    request: Request,
    jwt_handler: JWTHandlerDep,
    session: SessionDep,
    redis: RedisCacheDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),  # noqa: B008
) -> dict:
    # Extract token from Authorization header first, then fallback to cookie
    token = None
    if credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

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

    user_repo = PostgresUserRepository(session)
    user = await get_user_by_id(user_repo, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"id": user.id, "email": user.email, "role": user.role}


CurrentUser = Annotated[dict, Depends(get_current_user)]


async def get_optional_user(
    request: Request,
    jwt_handler: JWTHandlerDep,
    session: SessionDep,
    redis: RedisCacheDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),  # noqa: B008
) -> dict | None:
    """Get current user if authenticated, else return None (for guest access)."""
    # Extract token from Authorization header first, then fallback to cookie
    token = None
    if credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        return None

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

    user_repo = PostgresUserRepository(session)
    user = await get_user_by_id(user_repo, user_id)
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

    - Test environment (APP_ENV != "production"): No rate limiting
    - Production: Standard rate limiting

    Fails open if Redis is unavailable to ensure availability during outages.
    """
    # Skip rate limiting in non-production environments for load testing
    settings = get_settings()
    if settings.APP_ENV != "production":
        return

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

    - Test environment (APP_ENV != "production"): No rate limiting
    - Production: 100 requests per minute per IP (increased from 5 for better UX)

    Fails closed for security - returns 503 if Redis unavailable.
    """
    # Skip rate limiting in non-production environments for load testing
    settings = get_settings()
    if settings.APP_ENV != "production":
        return

    # Get client IP using trusted proxy-aware extraction
    trusted_proxies = settings.get_trusted_proxies()
    client_ip = extract_client_ip(request, trusted_proxies)

    key = f"auth_rate:{client_ip}"

    try:
        first_request = await redis.client.set(key, 1, ex=60, nx=True)
        if first_request:
            return

        count = await redis.client.incr(key)
        if count > 100:  # 100 attempts per minute (increased from 5)
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


async def check_guest_rate_limit(
    request: Request,
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
) -> None:
    """Rate limiting for guest chat endpoints using IP address.

    More restrictive than regular rate limiting:
    - 20 requests per minute for guest chat

    Fails closed for security - returns 503 if Redis unavailable.
    """
    # Get client IP using trusted proxy-aware extraction
    settings = get_settings()
    trusted_proxies = settings.get_trusted_proxies()
    client_ip = extract_client_ip(request, trusted_proxies)

    key = f"guest:{client_ip}"

    try:
        if not await redis.check_rate_limit(key, max_requests=20):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Guest rate limit exceeded. Please try again later.",
            )
    except RedisError as e:
        # Fail closed for guest endpoints - security over availability
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat temporarily unavailable. Please try again later.",
        ) from e


GuestRateLimitDep = Annotated[None, Depends(check_guest_rate_limit)]


# ============================================================================
# Strict app.state dependency accessors (no fallback construction)
# ============================================================================


def get_rag_agent(request: Request) -> Any:
    """Get RAG agent from app.state singleton via Request.

    Raises HTTPException 503 if not initialized - no fallback construction.
    """
    if hasattr(request.app.state, "rag_agent"):
        return request.app.state.rag_agent
    raise HTTPException(status_code=503, detail="RAG agent not initialized")


RagAgentDep = Annotated[Any, Depends(get_rag_agent)]


def get_llm_provider(request: Request) -> Any:
    """Get LLM provider from app.state singleton via Request.

    Raises HTTPException 503 if not initialized - no fallback construction.
    """
    if hasattr(request.app.state, "llm_provider"):
        return request.app.state.llm_provider
    raise HTTPException(status_code=503, detail="LLM provider not initialized")


LLMProviderDep = Annotated[Any, Depends(get_llm_provider)]


def get_es_client_dep(request: Request) -> ElasticsearchClient:
    """Get Elasticsearch client from app.state singleton via Request.

    Raises HTTPException 503 if not initialized - no fallback construction.
    """
    if hasattr(request.app.state, "es_client"):
        return request.app.state.es_client
    raise HTTPException(status_code=503, detail="Elasticsearch client not initialized")


ESClientDep = Annotated[ElasticsearchClient, Depends(get_es_client_dep)]


def get_embeddings_dep(request: Request) -> Any:
    """Get embeddings from app.state singleton via Request.

    Raises HTTPException 503 if not initialized - no fallback construction.
    """
    if hasattr(request.app.state, "embeddings"):
        return request.app.state.embeddings
    raise HTTPException(status_code=503, detail="Embeddings not initialized")


EmbeddingsDep = Annotated[Any, Depends(get_embeddings_dep)]


def get_unified_indexing_service_dep(request: Request) -> UnifiedIndexingService:
    """Get unified indexing service from app.state singleton via Request.

    Raises HTTPException 503 if not initialized - no fallback construction.
    """
    if hasattr(request.app.state, "unified_indexing_service"):
        return request.app.state.unified_indexing_service
    raise HTTPException(status_code=503, detail="Unified indexing service not initialized")


UnifiedIndexingServiceDep = Annotated[UnifiedIndexingService, Depends(get_unified_indexing_service_dep)]
