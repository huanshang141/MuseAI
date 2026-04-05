import pytest
from pydantic import ValidationError


def test_settings_requires_jwt_secret_in_production(monkeypatch):
    """JWT_SECRET should be required when APP_ENV is production."""
    # Clear any existing env vars
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    from app.config.settings import Settings

    with pytest.raises(ValidationError, match="JWT_SECRET must be set"):
        Settings(_env_file=None)


def test_settings_requires_llm_api_key_in_production(monkeypatch):
    """LLM_API_KEY should be required when APP_ENV is production."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)  # Valid secret

    from app.config.settings import Settings

    with pytest.raises(ValidationError, match="LLM_API_KEY must be set"):
        Settings(_env_file=None)


def test_settings_validates_jwt_secret_length(monkeypatch):
    """JWT_SECRET must be at least 32 characters in production."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "short")  # Too short
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    from app.config.settings import Settings

    with pytest.raises(ValidationError, match="JWT_SECRET must be at least 32 characters"):
        Settings(_env_file=None)


def test_settings_allows_defaults_in_development(monkeypatch):
    """In development mode, defaults are acceptable."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    from app.config.settings import Settings

    settings = Settings(_env_file=None)
    assert settings.JWT_SECRET == "dev-secret-do-not-use-in-production"
    assert settings.LLM_API_KEY == "dev-key-do-not-use-in-production"


def test_settings_defaults():
    from app.config.settings import Settings

    settings = Settings(
        APP_NAME="TestApp",
        APP_ENV="test",
        DEBUG=True,
        DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
        REDIS_URL="redis://localhost/0",
        ELASTICSEARCH_URL="http://localhost:9200",
        JWT_SECRET="test-secret",
        JWT_ALGORITHM="HS256",
        JWT_EXPIRE_MINUTES=60,
        LLM_PROVIDER="openai_compatible",
        LLM_BASE_URL="https://api.example.com",
        LLM_API_KEY="test-key",
        LLM_MODEL="test-model",
        EMBEDDING_PROVIDER="ollama",
        EMBEDDING_OLLAMA_BASE_URL="http://localhost:11434",
        EMBEDDING_OLLAMA_MODEL="test-embedding",
        ELASTICSEARCH_INDEX="test_index",
        EMBEDDING_DIMS=768,
    )
    assert settings.APP_NAME == "TestApp"
    assert settings.EMBEDDING_DIMS == 768


def test_settings_validation_embedding_dims():
    from app.config.settings import Settings

    with pytest.raises(ValueError):
        Settings(
            APP_NAME="TestApp",
            APP_ENV="test",
            DEBUG=True,
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            REDIS_URL="redis://localhost/0",
            ELASTICSEARCH_URL="http://localhost:9200",
            JWT_SECRET="test-secret",
            JWT_ALGORITHM="HS256",
            JWT_EXPIRE_MINUTES=60,
            LLM_PROVIDER="openai_compatible",
            LLM_BASE_URL="https://api.example.com",
            LLM_API_KEY="test-key",
            LLM_MODEL="test-model",
            EMBEDDING_PROVIDER="ollama",
            EMBEDDING_OLLAMA_BASE_URL="http://localhost:11434",
            EMBEDDING_OLLAMA_MODEL="test-embedding",
            ELASTICSEARCH_INDEX="test_index",
            EMBEDDING_DIMS=0,
        )


def test_settings_has_admin_emails():
    """Test that Settings has ADMIN_EMAILS field."""
    from app.config.settings import Settings

    settings = Settings()
    assert hasattr(settings, "ADMIN_EMAILS")
    assert isinstance(settings.ADMIN_EMAILS, str)


def test_settings_parses_admin_emails_from_string():
    """Test that ADMIN_EMAILS is parsed from comma-separated string via get_admin_emails()."""
    from app.config.settings import Settings

    settings = Settings(ADMIN_EMAILS="admin@example.com,another@example.com")
    assert settings.get_admin_emails() == ["admin@example.com", "another@example.com"]


def test_settings_admin_emails_defaults_to_empty():
    """Test that ADMIN_EMAILS defaults to empty list via get_admin_emails()."""
    from app.config.settings import Settings

    settings = Settings()
    assert settings.get_admin_emails() == []


def test_settings_admin_emails_from_env(monkeypatch):
    """Test that ADMIN_EMAILS can be set from environment variable."""
    monkeypatch.setenv("ADMIN_EMAILS", "admin1@example.com,admin2@example.com")

    from app.config.settings import Settings

    settings = Settings(_env_file=None)
    assert settings.get_admin_emails() == ["admin1@example.com", "admin2@example.com"]
