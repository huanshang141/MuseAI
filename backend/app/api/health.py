from fastapi import APIRouter, Request, Response
from loguru import logger
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import text

from app.config.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check service health")
async def health(request: Request) -> dict:
    degraded = list(request.app.state.degraded) if hasattr(request.app.state, "degraded") else []
    status = "healthy" if not degraded else "degraded"
    return {"status": status, "degraded_services": degraded}


async def _check_database() -> str:
    try:
        from app.infra.postgres.database import _engine

        if _engine is None:
            logger.warning("Database engine not initialized")
            return "not_initialized"

        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "healthy"
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        return "unhealthy"


async def _check_elasticsearch(request: Request) -> str:
    try:
        if not hasattr(request.app.state, "es_client"):
            logger.warning("Elasticsearch client not initialized")
            return "not_initialized"

        es_client = request.app.state.es_client
        if await es_client.health_check():
            return "healthy"
        return "unhealthy"
    except Exception as exc:
        logger.error(f"Elasticsearch health check failed: {exc}")
        return "unhealthy"


async def _check_redis() -> str:
    status = "unhealthy"
    client = None
    try:
        settings = get_settings()
        client = redis_from_url(settings.REDIS_URL)
        status = "healthy" if await client.ping() else "unhealthy"
    except Exception as exc:
        logger.error(f"Redis health check failed: {exc}")
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception as exc:
                logger.error(f"Redis client close failed: {exc}")
                status = "unhealthy"

    return status


@router.get("/ready", summary="Check service readiness")
async def ready(request: Request, response: Response) -> dict:
    checks = {
        "database": await _check_database(),
        "elasticsearch": await _check_elasticsearch(request),
        "redis": await _check_redis(),
    }

    if any(status != "healthy" for status in checks.values()):
        response.status_code = 503

    return checks
