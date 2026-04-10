import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

APP_MAIN_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"


def _load_isolated_app():
    from app.config.settings import reset_settings
    reset_settings()
    module_name = f"app_main_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, APP_MAIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def test_cors_uses_settings_origins(monkeypatch):
    """CORS should use CORS_ORIGINS from settings."""
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com,https://app.example.com")
    monkeypatch.setenv("APP_ENV", "development")

    app = _load_isolated_app()

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

    app = _load_isolated_app()

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
