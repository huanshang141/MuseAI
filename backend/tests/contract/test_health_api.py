import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_ready_endpoint_database_not_initialized():
    with patch("app.infra.postgres.database._engine", None):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["database"] == "not_initialized"
        assert data["elasticsearch"] == "not_configured"
        assert data["redis"] == "not_configured"


@pytest.mark.asyncio
async def test_ready_endpoint_database_healthy():
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=None)

    @asynccontextmanager
    async def mock_connect():
        yield mock_conn

    mock_engine = MagicMock()
    mock_engine.connect = mock_connect

    with patch("app.infra.postgres.database._engine", mock_engine):
        from app.api.health import ready
        from fastapi import Response

        response = Response()
        result = await ready(response)

        assert result["database"] == "healthy"
        assert result["elasticsearch"] == "not_configured"
        assert result["redis"] == "not_configured"
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_ready_endpoint_database_unhealthy():
    mock_engine = MagicMock()

    @asynccontextmanager
    async def mock_connect():
        raise Exception("Connection refused")
        yield

    mock_engine.connect = mock_connect

    with patch("app.infra.postgres.database._engine", mock_engine):
        from app.api.health import ready
        from fastapi import Response

        response = Response()
        result = await ready(response)

        assert result["database"] == "unhealthy"
        assert response.status_code == 503
