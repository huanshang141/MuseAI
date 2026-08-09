from pathlib import Path

import pytest
from pydantic import ValidationError


def test_nginx_caps_all_tour_session_bodies_including_creation():
    config = (Path(__file__).resolve().parents[3] / "deploy" / "nginx.conf").read_text(encoding="utf-8")

    location = config.split("location /api/v1/tour/sessions {", 1)[1].split("}", 1)[0]
    assert "client_max_body_size 2m;" in location


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
    """In development mode, defaults are acceptable when ALLOW_INSECURE_DEV_DEFAULTS is true."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_INSECURE_DEV_DEFAULTS", "true")
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


def test_settings_llm_model_split_defaults(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_TOUR_MODEL", raising=False)
    monkeypatch.delenv("LLM_REPORT_MODEL", raising=False)

    from app.config.settings import Settings

    settings = Settings(_env_file=None, ALLOW_INSECURE_DEV_DEFAULTS=True)

    assert settings.LLM_MODEL == "qwen-flash"
    assert settings.LLM_TOUR_MODEL == "qwen-flash"
    assert settings.LLM_REPORT_MODEL == "qwen-plus"
    assert settings.LLM_PROVIDER == "qwen"
    assert settings.LLM_COMPAT_MODE == "qwen"


def test_settings_accepts_qwen_compat_config():
    from app.config.settings import Settings

    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        JWT_SECRET="test-secret",
        LLM_PROVIDER="qwen",
        LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1",
        LLM_API_KEY="test-key",
        LLM_MODEL="qwen-flash",
        LLM_TOUR_MODEL="qwen-flash",
        LLM_REPORT_MODEL="qwen-plus",
        LLM_COMPAT_MODE="qwen",
    )

    assert settings.LLM_PROVIDER == "qwen"
    assert settings.LLM_COMPAT_MODE == "qwen"


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


def test_settings_rejects_wildcard_cors_in_production(monkeypatch):
    """CORS_ORIGINS should not allow wildcard in production."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("RERANK_PROVIDER", "mock")
    monkeypatch.setenv("TTS_ENABLED", "false")

    from app.config.settings import Settings

    with pytest.raises(ValidationError, match="CORS_ORIGINS cannot be wildcard in production"):
        Settings(_env_file=None)


def test_settings_requires_secrets_without_insecure_dev_flag(monkeypatch):
    """Without ALLOW_INSECURE_DEV_DEFAULTS, secrets must be explicitly set."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_INSECURE_DEV_DEFAULTS", "false")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    from app.config.settings import Settings

    with pytest.raises(ValidationError, match="JWT_SECRET must be set unless ALLOW_INSECURE_DEV_DEFAULTS=true"):
        Settings(_env_file=None)


def test_settings_accepts_matching_compose_postgres_settings():
    from app.config.settings import Settings

    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        JWT_SECRET="test-secret",
        LLM_API_KEY="test-key",
        DATABASE_URL="postgresql+asyncpg://museai:p%40ssword@localhost:5432/museai",
        POSTGRES_USER="museai",
        POSTGRES_PASSWORD="p@ssword",
        POSTGRES_DB="museai",
    )

    assert settings.POSTGRES_USER == "museai"
    assert settings.POSTGRES_PASSWORD is not None
    assert settings.POSTGRES_PASSWORD.get_secret_value() == "p@ssword"
    assert "p@ssword" not in repr(settings)
    assert "p%40ssword" not in repr(settings)
    assert "p@ssword" not in repr(settings.model_dump())
    assert "p%40ssword" not in repr(settings.model_dump())
    assert "DATABASE_URL" not in settings.model_dump()
    assert "POSTGRES_PASSWORD" not in settings.model_dump()


def test_env_example_is_accepted_by_application_settings():
    from app.config.settings import Settings

    env_example = Path(__file__).resolve().parents[3] / ".env.example"
    settings = Settings(
        _env_file=env_example,
        APP_ENV="test",
        JWT_SECRET="test-secret",
        LLM_API_KEY="test-key",
    )

    assert settings.POSTGRES_USER == "museai"
    assert settings.POSTGRES_PASSWORD is not None
    assert settings.POSTGRES_PASSWORD.get_secret_value() == "CHANGE_ME_STRONG_PASSWORD"
    assert settings.POSTGRES_DB == "museai"


@pytest.mark.parametrize("missing", ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"])
def test_settings_rejects_partial_compose_postgres_settings(missing):
    from app.config.settings import Settings

    compose_settings = {
        "POSTGRES_USER": "museai",
        "POSTGRES_PASSWORD": "strong-password",
        "POSTGRES_DB": "museai",
    }
    compose_settings.pop(missing)

    with pytest.raises(ValidationError, match="must be set together"):
        Settings(
            _env_file=None,
            APP_ENV="test",
            JWT_SECRET="test-secret",
            LLM_API_KEY="test-key",
            DATABASE_URL="postgresql+asyncpg://museai:strong-password@localhost:5432/museai",
            **compose_settings,
        )


@pytest.mark.parametrize(
    ("override", "expected_field"),
    [
        ({"POSTGRES_USER": "other"}, "POSTGRES_USER"),
        ({"POSTGRES_PASSWORD": "other"}, "POSTGRES_PASSWORD"),
        ({"POSTGRES_DB": "other"}, "POSTGRES_DB"),
    ],
)
def test_settings_rejects_compose_postgres_mismatch(override, expected_field):
    from app.config.settings import Settings

    compose_settings = {
        "POSTGRES_USER": "museai",
        "POSTGRES_PASSWORD": "strong-password",
        "POSTGRES_DB": "museai",
    }
    compose_settings.update(override)

    with pytest.raises(ValidationError, match=rf"{expected_field} must match DATABASE_URL"):
        Settings(
            _env_file=None,
            APP_ENV="test",
            JWT_SECRET="test-secret",
            LLM_API_KEY="test-key",
            DATABASE_URL="postgresql+asyncpg://museai:strong-password@localhost:5432/museai",
            **compose_settings,
        )


def test_settings_still_rejects_unknown_settings():
    from app.config.settings import Settings

    assert Settings.model_config["extra"] == "forbid"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Settings(
            _env_file=None,
            APP_ENV="test",
            JWT_SECRET="test-secret",
            LLM_API_KEY="test-key",
            UNEXPECTED_SETTING="not-allowed",
        )


def test_settings_rejects_postgresql_prefix_lookalike_driver():
    from app.config.settings import Settings

    with pytest.raises(ValidationError, match="DATABASE_URL must use PostgreSQL"):
        Settings(
            _env_file=None,
            APP_ENV="test",
            JWT_SECRET="test-secret",
            LLM_API_KEY="test-key",
            DATABASE_URL="postgresqlx://museai:strong-password@localhost:5432/museai",
            POSTGRES_USER="museai",
            POSTGRES_PASSWORD="strong-password",
            POSTGRES_DB="museai",
        )


def test_compose_mismatch_validation_error_hides_credential_inputs():
    from app.config.settings import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            APP_ENV="test",
            JWT_SECRET="jwt-secret-value",
            LLM_API_KEY="llm-secret-value",
            DATABASE_URL="postgresql+asyncpg://museai:url-secret@localhost:5432/museai",
            POSTGRES_USER="museai",
            POSTGRES_PASSWORD="different-secret",
            POSTGRES_DB="museai",
        )

    rendered = str(exc_info.value) + exc_info.value.json()
    assert "jwt-secret-value" not in rendered
    assert "llm-secret-value" not in rendered
    assert "url-secret" not in rendered
    assert "different-secret" not in rendered


def test_settings_repr_and_dump_exclude_configured_secrets():
    from app.config.settings import Settings

    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        JWT_SECRET="jwt-secret-value",
        LLM_API_KEY="llm-secret-value",
        EMBEDDING_OPENAI_API_KEY="embedding-secret-value",
        RERANK_API_KEY="rerank-secret-value",
        TTS_API_KEY="tts-secret-value",
    )

    rendered = repr(settings) + repr(settings.model_dump())
    for secret in (
        "jwt-secret-value",
        "llm-secret-value",
        "embedding-secret-value",
        "rerank-secret-value",
        "tts-secret-value",
    ):
        assert secret not in rendered
