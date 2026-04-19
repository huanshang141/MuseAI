from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint():
    app.state.degraded = set()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["degraded_services"] == []


def _healthy_engine() -> MagicMock:
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=None)

    @asynccontextmanager
    async def mock_connect():
        yield mock_conn

    mock_engine = MagicMock()
    mock_engine.connect = mock_connect
    return mock_engine


def _unhealthy_engine() -> MagicMock:
    @asynccontextmanager
    async def mock_connect():
        raise Exception("Connection refused")
        yield

    mock_engine = MagicMock()
    mock_engine.connect = mock_connect
    return mock_engine


class _MockESClient:
    def __init__(self, *, healthy: bool = True, error: Exception | None = None):
        self._healthy = healthy
        self._error = error

    async def health_check(self) -> bool:
        if self._error:
            raise self._error
        return self._healthy


class _MockRedisClient:
    def __init__(
        self,
        *,
        healthy: bool = True,
        error: Exception | None = None,
        close_error: Exception | None = None,
    ):
        self._healthy = healthy
        self._error = error
        self._close_error = close_error
        self.closed = False

    async def ping(self) -> bool:
        if self._error:
            raise self._error
        return self._healthy

    async def aclose(self) -> None:
        if self._close_error:
            raise self._close_error
        self.closed = True


async def _call_ready() -> tuple[int, dict]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ready")
    return response.status_code, response.json()


@pytest.mark.asyncio
async def test_ready_all_healthy_returns_200():
    redis_client = _MockRedisClient(healthy=True)
    with (
        patch("app.infra.postgres.database._engine", _healthy_engine()),
        patch("app.api.health.redis_from_url", return_value=redis_client),
    ):
        status_code, data = await _call_ready()

    assert status_code == 200
    assert data == {"database": "healthy", "elasticsearch": "healthy", "redis": "healthy"}
    assert redis_client.closed is True


@pytest.mark.asyncio
async def test_ready_returns_503_when_elasticsearch_unhealthy():
    from unittest.mock import AsyncMock

    from app.main import app

    # Configure ES mock to return unhealthy
    app.state.es_client.health_check = AsyncMock(return_value=False)

    with (
        patch("app.infra.postgres.database._engine", _healthy_engine()),
        patch("app.api.health.redis_from_url", return_value=_MockRedisClient(healthy=True)),
    ):
        status_code, data = await _call_ready()

    assert status_code == 503
    assert data["database"] == "healthy"
    assert data["elasticsearch"] == "unhealthy"
    assert data["redis"] == "healthy"

    # Reset to healthy
    app.state.es_client.health_check = AsyncMock(return_value=True)


@pytest.mark.asyncio
async def test_ready_returns_503_when_redis_unhealthy():
    with (
        patch("app.infra.postgres.database._engine", _healthy_engine()),
        patch("app.api.health.redis_from_url", return_value=_MockRedisClient(healthy=False)),
    ):
        status_code, data = await _call_ready()

    assert status_code == 503
    assert data["database"] == "healthy"
    assert data["elasticsearch"] == "healthy"
    assert data["redis"] == "unhealthy"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "engine,status",
    [
        (None, "not_initialized"),
        (_unhealthy_engine(), "unhealthy"),
    ],
)
async def test_ready_returns_503_when_database_not_ready(engine, status):
    with (
        patch("app.infra.postgres.database._engine", engine),
        patch("app.api.health.redis_from_url", return_value=_MockRedisClient(healthy=True)),
    ):
        status_code, data = await _call_ready()

    assert status_code == 503
    assert data["database"] == status
    assert data["elasticsearch"] == "healthy"
    assert data["redis"] == "healthy"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "es_error,redis_error,expected_es,expected_redis",
    [
        (Exception("es boom"), None, "unhealthy", "healthy"),
        (None, Exception("redis boom"), "healthy", "unhealthy"),
    ],
)
async def test_ready_handles_probe_exceptions(es_error, redis_error, expected_es, expected_redis):
    from unittest.mock import AsyncMock

    from app.main import app

    # Configure ES mock behavior
    if es_error:
        app.state.es_client.health_check = AsyncMock(side_effect=es_error)
    else:
        app.state.es_client.health_check = AsyncMock(return_value=True)

    with (
        patch("app.infra.postgres.database._engine", _healthy_engine()),
        patch("app.api.health.redis_from_url", return_value=_MockRedisClient(healthy=True, error=redis_error)),
    ):
        status_code, data = await _call_ready()

    assert status_code == 503
    assert data["database"] == "healthy"
    assert data["elasticsearch"] == expected_es
    assert data["redis"] == expected_redis

    # Reset
    app.state.es_client.health_check = AsyncMock(return_value=True)


@pytest.mark.asyncio
async def test_ready_returns_503_when_redis_close_raises_after_healthy_ping():
    redis_client = _MockRedisClient(healthy=True, close_error=Exception("close boom"))
    with (
        patch("app.infra.postgres.database._engine", _healthy_engine()),
        patch("app.api.health.redis_from_url", return_value=redis_client),
    ):
        status_code, data = await _call_ready()

    assert status_code == 503
    assert data["database"] == "healthy"
    assert data["elasticsearch"] == "healthy"
    assert data["redis"] == "unhealthy"


@pytest.mark.asyncio
async def test_health_returns_degraded_when_services_degraded():
    app.state.degraded = {"elasticsearch"}
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert "elasticsearch" in data["degraded_services"]
    finally:
        app.state.degraded = set()


@pytest.mark.asyncio
async def test_health_returns_healthy_when_no_services_degraded():
    app.state.degraded = set()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["degraded_services"] == []
