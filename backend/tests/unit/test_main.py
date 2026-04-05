import pytest
from fastapi.testclient import TestClient


def test_cors_uses_settings_origins(monkeypatch):
    """CORS should use CORS_ORIGINS from settings."""
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com,https://app.example.com")
    monkeypatch.setenv("APP_ENV", "development")

    from app.main import app

    # Check that CORS middleware is configured
    client = TestClient(app)
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    # Should allow the configured origin
    assert "access-control-allow-origin" in response.headers


def test_cors_rejects_unauthorized_origin_in_production(monkeypatch):
    """In production, CORS should reject unauthorized origins."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")

    # Need to reimport to pick up new settings
    import importlib

    import app.main

    importlib.reload(app.main)

    from app.main import app

    client = TestClient(app)
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://malicious.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    # Should NOT allow unauthorized origin
    assert response.headers.get("access-control-allow-origin") != "https://malicious.com"
