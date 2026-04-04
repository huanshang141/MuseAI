import logging

from fastapi import APIRouter, Response
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict:
    checks = {}
    all_healthy = True

    try:
        from app.infra.postgres.database import _engine

        if _engine:
            async with _engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = "healthy"
        else:
            logger.warning("Database engine not initialized")
            checks["database"] = "not_initialized"
            all_healthy = False
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = "unhealthy"
        all_healthy = False

    checks["elasticsearch"] = "not_configured"
    checks["redis"] = "not_configured"

    if not all_healthy:
        response.status_code = 503

    return checks
