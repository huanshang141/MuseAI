import json
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
        v = v.strip().lower()
        allowed = {"development", "test", "local", "production"}
        if v not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}, got {v!r}")
        return v
    DEBUG: bool = False  # Changed: Default to False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, v: object) -> object:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized == "release":
                return False
            if normalized == "debug":
                return True
        return v

    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    REDIS_URL: str = "redis://localhost:6379"
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    JWT_SECRET: str = ""  # Changed: No default
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    LLM_PROVIDER: str = "openai_compatible"
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_API_KEY: str = ""  # Changed: No default
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_TOUR_MODEL: str = "deepseek-v4-flash"
    LLM_REPORT_MODEL: str = "deepseek-v4-pro"
    LLM_HEADERS: str = ""  # JSON string of extra headers, e.g. '{"User-Agent": "curl/8.5.0"}'
    LLM_TEMPERATURE: float = 0.6
    LLM_MAX_TOKENS: int = 800  # 0 = no limit
    LLM_ENABLE_THINKING: bool = False  # When False, explicitly passes thinking=disabled to the API

    @field_validator("LLM_PROVIDER")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        v = v.strip().lower()
        allowed = {"openai_compatible", "openai", "deepseek"}
        if v not in allowed:
            raise ValueError(f"LLM_PROVIDER must be one of {allowed}, got {v!r}")
        return v

    @field_validator("LLM_HEADERS")
    @classmethod
    def validate_llm_headers(cls, v: str) -> str:
        if not v:
            return v
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM_HEADERS must be a valid JSON object string") from exc
        if not isinstance(parsed, dict):
            raise ValueError("LLM_HEADERS must be a JSON object")
        return v

    @field_validator("LLM_MODEL", "LLM_TOUR_MODEL", "LLM_REPORT_MODEL")
    @classmethod
    def validate_llm_model_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("LLM model name cannot be empty")
        return v

    @field_validator("LLM_TEMPERATURE")
    @classmethod
    def validate_llm_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"LLM_TEMPERATURE must be between 0 and 2, got {v}")
        return v

    @field_validator("LLM_MAX_TOKENS")
    @classmethod
    def validate_llm_max_tokens(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"LLM_MAX_TOKENS must be >= 0, got {v}")
        return v

    EMBEDDING_PROVIDER: str = "ollama"  # ollama, openai
    EMBEDDING_OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBEDDING_OLLAMA_MODEL: str = "nomic-embed-text"
    EMBEDDING_OPENAI_BASE_URL: str = ""
    EMBEDDING_OPENAI_API_KEY: str = ""
    EMBEDDING_OPENAI_MODEL: str = ""

    @field_validator("EMBEDDING_PROVIDER")
    @classmethod
    def validate_embedding_provider(cls, v: str) -> str:
        v = v.strip().lower()
        allowed = {"ollama", "openai"}
        if v not in allowed:
            raise ValueError(f"EMBEDDING_PROVIDER must be one of {allowed}, got {v!r}")
        return v

    ELASTICSEARCH_INDEX: str = "museai_chunks_v1"
    EMBEDDING_DIMS: int = 768

    @field_validator("EMBEDDING_DIMS")
    @classmethod
    def validate_embedding_dims(cls, v: int) -> int:
        if v <= 0 or v > 4096:
            raise ValueError(f"EMBEDDING_DIMS must be between 1 and 4096, got {v}")
        return v

    # Rerank服务配置
    RERANK_PROVIDER: str = "siliconflow"  # siliconflow, openai, cohere, custom, mock
    RERANK_BASE_URL: str = ""
    RERANK_API_KEY: str = ""
    RERANK_MODEL: str = "rerank-v1"
    RERANK_TOP_N: int = 10

    @field_validator("RERANK_PROVIDER")
    @classmethod
    def validate_rerank_provider(cls, v: str) -> str:
        v = v.strip().lower()
        allowed = {"siliconflow", "openai", "cohere", "custom", "mock"}
        if v not in allowed:
            raise ValueError(f"RERANK_PROVIDER must be one of {allowed}, got {v!r}")
        return v

    # TTS服务配置
    TTS_ENABLED: bool = True
    TTS_PROVIDER: str = "xiaomi"  # xiaomi, mock
    TTS_BASE_URL: str = "https://api.xiaomimimo.com/v1"
    TTS_API_KEY: str = ""
    TTS_MODEL: str = "mimo-v2.5-tts"
    TTS_DEFAULT_VOICE: str = "冰糖"
    TTS_TIMEOUT: float = 30.0
    TTS_VOICE_DESIGN_MODEL: str = "mimo-v2.5-tts-voicedesign"

    @field_validator("TTS_PROVIDER")
    @classmethod
    def validate_tts_provider(cls, v: str) -> str:
        v = v.strip().lower()
        allowed = {"xiaomi", "mock"}
        if v not in allowed:
            raise ValueError(f"TTS_PROVIDER must be one of {allowed}, got {v!r}")
        return v

    @field_validator("TTS_TIMEOUT")
    @classmethod
    def validate_tts_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"TTS_TIMEOUT must be positive, got {v}")
        return v

    # 动态文档过滤配置
    RETRIEVAL_TOP_K: int = 15
    RERANK_ABSOLUTE_THRESHOLD: float = 0.25
    RERANK_RELATIVE_GAP: float = 0.25
    RERANK_MIN_DOCS: int = 1
    RERANK_MAX_DOCS: int = 8

    @field_validator("RETRIEVAL_TOP_K", "RERANK_TOP_N", "RERANK_MIN_DOCS", "RERANK_MAX_DOCS")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"must be positive, got {v}")
        return v

    @field_validator("RERANK_ABSOLUTE_THRESHOLD", "RERANK_RELATIVE_GAP")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"must be between 0 and 1, got {v}")
        return v

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
        v_upper = v.strip().upper()
        if v_upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got {v!r}")
        return v_upper
    LOG_DIR: str = "logs"
    LOG_FORMAT: str = "json"  # "json" or "text"

    @field_validator("LOG_FORMAT")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        v = v.strip().lower()
        allowed = {"json", "text"}
        if v not in allowed:
            raise ValueError(f"LOG_FORMAT must be one of {allowed}, got {v!r}")
        return v

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
            if self.RERANK_PROVIDER != "mock" and not self.RERANK_API_KEY:
                raise ValueError("RERANK_API_KEY must be set when RERANK_PROVIDER is configured in production")
            if self.TTS_ENABLED and self.TTS_PROVIDER != "mock" and not self.TTS_API_KEY:
                raise ValueError("TTS_API_KEY must be set when TTS_PROVIDER is configured in production")
            if self.CORS_ORIGINS.strip() == "*":
                raise ValueError("CORS_ORIGINS cannot be wildcard in production")
            if self.ADMIN_EMAILS.strip():
                warnings.warn(
                    "ADMIN_EMAILS is deprecated in production; use scripts/bootstrap_admin.py.",
                    DeprecationWarning,
                    stacklevel=2,
                )

        if self.JWT_EXPIRE_MINUTES <= 0:
            raise ValueError("JWT_EXPIRE_MINUTES must be positive")
        if self.RERANK_MIN_DOCS > self.RERANK_MAX_DOCS:
            raise ValueError("RERANK_MIN_DOCS cannot be greater than RERANK_MAX_DOCS")
        if self.RERANK_MAX_DOCS > self.RERANK_TOP_N:
            raise ValueError("RERANK_MAX_DOCS cannot be greater than RERANK_TOP_N")

        if self.EMBEDDING_PROVIDER == "openai":
            if not self.EMBEDDING_OPENAI_BASE_URL:
                raise ValueError("EMBEDDING_OPENAI_BASE_URL must be set when EMBEDDING_PROVIDER=openai")
            if not self.EMBEDDING_OPENAI_API_KEY:
                raise ValueError("EMBEDDING_OPENAI_API_KEY must be set when EMBEDDING_PROVIDER=openai")
            if not self.EMBEDDING_OPENAI_MODEL:
                raise ValueError("EMBEDDING_OPENAI_MODEL must be set when EMBEDDING_PROVIDER=openai")

        if self.RERANK_PROVIDER in {"openai", "cohere", "custom"} and not self.RERANK_BASE_URL:
            raise ValueError("RERANK_BASE_URL must be set for OpenAI-compatible rerank providers")

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
        origins = self.CORS_ORIGINS.strip()
        if origins == "*":
            return ["*"]
        return [origin.strip() for origin in origins.split(",") if origin.strip()]


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reset_settings() -> None:
    global _settings_instance
    _settings_instance = None
