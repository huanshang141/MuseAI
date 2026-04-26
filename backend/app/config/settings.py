import warnings
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory (where .env file is located)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
    )

    APP_NAME: str = "MuseAI"
    APP_ENV: str = "development"

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        allowed = {"development", "test", "local", "production"}
        if v not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}, got {v!r}")
        return v
    DEBUG: bool = False  # Changed: Default to False

    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    REDIS_URL: str = "redis://localhost:6379"
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    JWT_SECRET: str = ""  # Changed: No default
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    LLM_PROVIDER: str = "openai"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""  # Changed: No default
    LLM_MODEL: str = "gpt-4o-mini"

    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBEDDING_OLLAMA_MODEL: str = "nomic-embed-text"

    ELASTICSEARCH_INDEX: str = "museai_chunks_v1"
    EMBEDDING_DIMS: int = 768

    @field_validator("EMBEDDING_DIMS")
    @classmethod
    def validate_embedding_dims(cls, v: int) -> int:
        if v <= 0 or v > 4096:
            raise ValueError(f"EMBEDDING_DIMS must be between 1 and 4096, got {v}")
        return v

    # Rerank服务配置
    RERANK_PROVIDER: str = "openai"  # openai, cohere, custom
    RERANK_BASE_URL: str = ""
    RERANK_API_KEY: str = ""
    RERANK_MODEL: str = "rerank-v1"
    RERANK_TOP_N: int = 5  # 返回top N结果

    CHUNK_MERGE_ENABLED: bool = True
    CHUNK_MERGE_MAX_LEVEL: int = 1
    CHUNK_MERGE_MAX_PARENTS: int = 3

    # CORS settings
    CORS_ORIGINS: str = "http://localhost:3000"  # Comma-separated list or "*"
    CORS_ALLOW_CREDENTIALS: bool = True

    # Allow insecure dev defaults for local development
    ALLOW_INSECURE_DEV_DEFAULTS: bool = False
    RATE_LIMIT_ENABLED: bool = True

    # Logging settings
    LOG_LEVEL: str = "INFO"

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got {v!r}")
        return v_upper
    LOG_DIR: str = "logs"
    LOG_FORMAT: str = "json"  # "json" or "text"

    # Admin configuration (comma-separated list of admin email addresses)
    ADMIN_EMAILS: str = ""

    # Trusted proxy configuration for client IP extraction
    # Comma-separated list of trusted proxy/load balancer IPs
    # These IPs are trusted to send valid X-Forwarded-For headers
    TRUSTED_PROXIES: str = ""

    def get_admin_emails(self) -> list[str]:
        """Parse ADMIN_EMAILS setting into a list."""
        if not self.ADMIN_EMAILS:
            return []
        return [email.strip() for email in self.ADMIN_EMAILS.split(",") if email.strip()]

    def get_trusted_proxies(self) -> set[str]:
        """Parse TRUSTED_PROXIES setting into a set."""
        if not self.TRUSTED_PROXIES:
            return set()
        return {proxy.strip() for proxy in self.TRUSTED_PROXIES.split(",") if proxy.strip()}

    

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        is_production = self.APP_ENV == "production"
        allow_insecure_defaults = (
            self.ALLOW_INSECURE_DEV_DEFAULTS
            and self.APP_ENV in {"development", "test", "local"}
        )

        if is_production:
            if not self.JWT_SECRET:
                raise ValueError("JWT_SECRET must be set in production")
            if len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if not self.LLM_API_KEY:
                raise ValueError("LLM_API_KEY must be set in production")
            if self.RERANK_PROVIDER and not self.RERANK_API_KEY:
                raise ValueError("RERANK_API_KEY must be set when RERANK_PROVIDER is configured in production")
            if self.CORS_ORIGINS.strip() == "*":
                raise ValueError("CORS_ORIGINS cannot be wildcard in production")
            if self.ADMIN_EMAILS.strip():
                warnings.warn(
                    "ADMIN_EMAILS is deprecated in production; use scripts/bootstrap_admin.py.",
                    DeprecationWarning,
                    stacklevel=2,
                )

        # Development defaults (only if explicitly allowed)
        if not self.JWT_SECRET:
            if allow_insecure_defaults:
                self.JWT_SECRET = "dev-secret-do-not-use-in-production"
            else:
                raise ValueError("JWT_SECRET must be set unless ALLOW_INSECURE_DEV_DEFAULTS=true")
        if not self.LLM_API_KEY:
            if allow_insecure_defaults:
                self.LLM_API_KEY = "dev-key-do-not-use-in-production"
            else:
                raise ValueError("LLM_API_KEY must be set unless ALLOW_INSECURE_DEV_DEFAULTS=true")

        return self

    def get_cors_origins(self) -> list[str]:
        """Parse CORS_ORIGINS setting into a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reset_settings() -> None:
    global _settings_instance
    _settings_instance = None
