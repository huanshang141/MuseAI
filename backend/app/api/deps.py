import hashlib
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
    token = None
    if credentials:
        token = credentials.credentials

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

    return {"id": user.id if isinstance(user.id, str) else user.id.value, "email": user.email, "role": user.role}


CurrentUser = Annotated[dict, Depends(get_current_user)]


async def get_optional_user(
    request: Request,
    jwt_handler: JWTHandlerDep,
    session: SessionDep,
    redis: RedisCacheDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),  # noqa: B008
) -> dict | None:
    """Get current user if authenticated, else return None (for guest access)."""
    token = None
    if credentials:
        token = credentials.credentials

    if not token:
        return None

    # Check if token is blacklisted
    jti = jwt_handler.get_jti(token)
    if jti:
        try:
            if await redis.is_token_blacklisted(jti):
                return None
        except RedisError as e:
            logger.warning(f"Redis error during optional user blacklist check, fail-open: {e}")
            # In development, continue without blacklist check
            pass

    user_id = jwt_handler.verify_token(token)
    if user_id is None:
        return None

    user_repo = PostgresUserRepository(session)
    user = await get_user_by_id(user_repo, user_id)
    if user is None:
        return None

    return {"id": user.id if isinstance(user.id, str) else user.id.value, "email": user.email, "role": user.role}


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
    """Backward-compatible alias for role-based admin checks only."""
    return await get_current_admin(current_user)


CurrentAdminUser = Annotated[dict, Depends(get_current_admin_user)]


async def check_rate_limit(
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> None:
    """Check rate limit for the current user.

    - RATE_LIMIT_ENABLED=false: No rate limiting
    - Production: Standard rate limiting

    Fails open if Redis is unavailable to ensure availability during outages.
    """
    # Skip rate limiting when RATE_LIMIT_ENABLED is false
    settings = get_settings()
    if not settings.RATE_LIMIT_ENABLED:
        return

    try:
        if not await redis.check_rate_limit(current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
    except RedisError as e:
        logger.warning(f"Redis error during rate limit check, fail-open: {e}")
        # Log the error but allow request to proceed
        # This ensures availability during Redis outages
        pass


RateLimitDep = Annotated[None, Depends(check_rate_limit)]


async def check_auth_rate_limit(
    request: Request,
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
) -> None:
    """Rate limiting for authentication endpoints using IP address.

    - RATE_LIMIT_ENABLED=false: No rate limiting
    - Production: 100 requests per minute per IP (increased from 5 for better UX)

    Fails closed for security - returns 503 if Redis unavailable.
    """
    # Skip rate limiting when RATE_LIMIT_ENABLED is false
    settings = get_settings()
    if not settings.RATE_LIMIT_ENABLED:
        return

    # Get client IP using trusted proxy-aware extraction
    trusted_proxies = settings.get_trusted_proxies()
    client_ip = extract_client_ip(request, trusted_proxies)

    key = f"auth_rate:{client_ip}"

    try:
        if not await redis.check_rate_limit(key, max_requests=100, window_seconds=60):
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


async def check_tts_synthesize_rate_limit(
    request: Request,
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
) -> None:
    """Protect standalone TTS with a per-token bucket and shared-IP ceiling."""
    settings = get_settings()
    if not settings.RATE_LIMIT_ENABLED:
        return

    client_ip = extract_client_ip(request, settings.get_trusted_proxies())
    try:
        session_allowed = True
        session_token = request.headers.get("X-Session-Token")
        if session_token:
            token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
            session_allowed = await redis.check_rate_limit(
                f"tts_synthesize_session:{token_hash}",
                max_requests=settings.TTS_SYNTHESIZE_SESSION_RATE_LIMIT_PER_MINUTE,
                window_seconds=60,
            )
        ip_allowed = await redis.check_rate_limit(
            f"tts_synthesize_ip:{client_ip}",
            max_requests=settings.TTS_SYNTHESIZE_IP_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        if not session_allowed or not ip_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="TTS synthesis rate limit exceeded. Please try again later.",
            )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS synthesis is temporarily unavailable. Please try again later.",
        ) from exc


TTSSynthesizeRateLimitDep = Annotated[
    None,
    Depends(check_tts_synthesize_rate_limit),
]


async def check_tour_chat_rate_limit(
    request: Request,
    session_id: str,
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
) -> None:
    """Limit mini-program chat per tour session plus a Wi-Fi-safe IP ceiling."""
    settings = get_settings()
    if not settings.RATE_LIMIT_ENABLED:
        return

    trusted_proxies = settings.get_trusted_proxies()
    client_ip = extract_client_ip(request, trusted_proxies)
    try:
        session_allowed = await redis.check_rate_limit(
            f"tour_chat_session:{session_id}",
            max_requests=settings.TOUR_CHAT_SESSION_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        ip_allowed = await redis.check_rate_limit(
            f"tour_chat_ip:{client_ip}",
            max_requests=settings.TOUR_CHAT_IP_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        if not session_allowed or not ip_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Tour chat rate limit exceeded. Please try again later.",
            )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat temporarily unavailable. Please try again later.",
        ) from exc


TourChatRateLimitDep = Annotated[None, Depends(check_tour_chat_rate_limit)]


async def check_tour_session_create_rate_limit(
    request: Request,
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
) -> None:
    """Protect anonymous session creation with a shared-Wi-Fi-safe IP ceiling."""
    settings = get_settings()
    if not settings.RATE_LIMIT_ENABLED:
        return

    client_ip = extract_client_ip(request, settings.get_trusted_proxies())
    try:
        allowed = await redis.check_rate_limit(
            f"tour_session_create_ip:{client_ip}",
            max_requests=settings.TOUR_SESSION_CREATE_IP_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Tour session creation rate limit exceeded. Please try again later.",
            )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tour sessions are temporarily unavailable. Please try again later.",
        ) from exc


TourSessionCreateRateLimitDep = Annotated[
    None,
    Depends(check_tour_session_create_rate_limit),
]


async def check_tour_report_rate_limit(
    request: Request,
    session_id: str,
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
) -> None:
    """Limit report generation per session and across one public network."""
    settings = get_settings()
    if not settings.RATE_LIMIT_ENABLED:
        return

    client_ip = extract_client_ip(request, settings.get_trusted_proxies())
    try:
        session_allowed = await redis.check_rate_limit(
            f"tour_report_session:{session_id}",
            max_requests=settings.TOUR_REPORT_SESSION_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        ip_allowed = await redis.check_rate_limit(
            f"tour_report_ip:{client_ip}",
            max_requests=settings.TOUR_REPORT_IP_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        if not session_allowed or not ip_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Tour report rate limit exceeded. Please try again later.",
            )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tour reports are temporarily unavailable. Please try again later.",
        ) from exc


TourReportRateLimitDep = Annotated[None, Depends(check_tour_report_rate_limit)]


async def check_tour_session_write_rate_limit(
    request: Request,
    session_id: str,
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
) -> None:
    """Protect large anonymous session-state writes without penalizing museum Wi-Fi."""
    settings = get_settings()
    if not settings.RATE_LIMIT_ENABLED:
        return

    client_ip = extract_client_ip(request, settings.get_trusted_proxies())
    try:
        session_allowed = await redis.check_rate_limit(
            f"tour_session_write_session:{session_id}",
            max_requests=settings.TOUR_SESSION_WRITE_SESSION_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        ip_allowed = await redis.check_rate_limit(
            f"tour_session_write_ip:{client_ip}",
            max_requests=settings.TOUR_SESSION_WRITE_IP_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        if not session_allowed or not ip_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Tour session update rate limit exceeded. Please try again later.",
            )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tour session updates are temporarily unavailable. Please try again later.",
        ) from exc


TourSessionWriteRateLimitDep = Annotated[
    None,
    Depends(check_tour_session_write_rate_limit),
]


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
