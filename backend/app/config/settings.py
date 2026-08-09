import json
from pathlib import Path

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

# Project root directory (where .env file is located)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        hide_input_in_errors=True,
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

    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///:memory:", repr=False, exclude=True)
    # Docker Compose reads these values from the same root .env file. They are
    # optional for application-only deployments, but must be complete and agree
    # with DATABASE_URL whenever supplied.
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: SecretStr | None = Field(default=None, exclude=True)
    POSTGRES_DB: str | None = Field(default=None, validate_default=True)
    REDIS_URL: str = "redis://localhost:6379"
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    JWT_SECRET: str = Field(default="", repr=False, exclude=True)  # Changed: No default
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    LLM_PROVIDER: str = "qwen"
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_API_KEY: str = Field(default="", repr=False, exclude=True)  # Changed: No default
    LLM_MODEL: str = "qwen-flash"
    LLM_TOUR_MODEL: str = "qwen-flash"
    LLM_REPORT_MODEL: str = "qwen-plus"
    LLM_HEADERS: str = ""  # JSON string of extra headers, e.g. '{"User-Agent": "curl/8.5.0"}'
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 800  # 0 = no limit
    LLM_ENABLE_THINKING: bool = False  # When False, disables provider-specific thinking mode where supported
    LLM_COMPAT_MODE: str = "qwen"  # auto, openai, deepseek, qwen

    @field_validator("LLM_PROVIDER")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        v = v.strip().lower()
        allowed = {"openai_compatible", "openai", "deepseek", "qwen"}
        if v not in allowed:
            raise ValueError(f"LLM_PROVIDER must be one of {allowed}, got {v!r}")
        return v

    @field_validator("LLM_COMPAT_MODE")
    @classmethod
    def validate_llm_compat_mode(cls, v: str) -> str:
        v = v.strip().lower()
        allowed = {"auto", "openai", "deepseek", "qwen"}
        if v not in allowed:
            raise ValueError(f"LLM_COMPAT_MODE must be one of {allowed}, got {v!r}")
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
    EMBEDDING_OPENAI_API_KEY: str = Field(default="", repr=False, exclude=True)
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
    RERANK_API_KEY: str = Field(default="", repr=False, exclude=True)
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
    TTS_API_KEY: str = Field(default="", repr=False, exclude=True)
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

    # Uploaded exhibit images live outside the public web root and are served
    # through a validated API endpoint. Relative paths resolve from PROJECT_ROOT.
    EXHIBIT_IMAGE_DIR: Path = PROJECT_ROOT / "var" / "exhibit-images"
    EXHIBIT_IMAGE_MAX_BYTES: int = 5 * 1024 * 1024
    EXHIBIT_IMAGE_MAX_PIXELS: int = 40_000_000

    @field_validator("EXHIBIT_IMAGE_DIR", mode="before")
    @classmethod
    def normalize_exhibit_image_dir(cls, v: object) -> Path:
        path = Path(str(v)).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @field_validator("EXHIBIT_IMAGE_MAX_BYTES", "EXHIBIT_IMAGE_MAX_PIXELS")
    @classmethod
    def validate_image_limit(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("exhibit image limits must be positive")
        return v

    # Allow insecure dev defaults for local development
    ALLOW_INSECURE_DEV_DEFAULTS: bool = False
    RATE_LIMIT_ENABLED: bool = True
    TOUR_CHAT_SESSION_RATE_LIMIT_PER_MINUTE: int = 20
    TOUR_CHAT_IP_RATE_LIMIT_PER_MINUTE: int = 300
    TOUR_SESSION_CREATE_IP_RATE_LIMIT_PER_MINUTE: int = 300
    TOUR_REPORT_SESSION_RATE_LIMIT_PER_MINUTE: int = 6
    TOUR_REPORT_IP_RATE_LIMIT_PER_MINUTE: int = 120
    TOUR_SESSION_WRITE_SESSION_RATE_LIMIT_PER_MINUTE: int = 60
    TOUR_SESSION_WRITE_IP_RATE_LIMIT_PER_MINUTE: int = 600
    TTS_SYNTHESIZE_SESSION_RATE_LIMIT_PER_MINUTE: int = 30
    TTS_SYNTHESIZE_IP_RATE_LIMIT_PER_MINUTE: int = 300

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

    # Accepted only so older deployments can remove the variable without a
    # startup outage. It has no authorization effect and is not documented.
    ADMIN_EMAILS: str = ""

    @field_validator("LOG_FORMAT")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        v = v.strip().lower()
        allowed = {"json", "text"}
        if v not in allowed:
            raise ValueError(f"LOG_FORMAT must be one of {allowed}, got {v!r}")
        return v

    # Trusted proxy configuration for client IP extraction
    # Comma-separated list of trusted proxy/load balancer IPs
    # These IPs are trusted to send valid X-Forwarded-For headers
    TRUSTED_PROXIES: str = ""

    def get_trusted_proxies(self) -> set[str]:
        """Parse TRUSTED_PROXIES setting into a set."""
        if not self.TRUSTED_PROXIES:
            return set()
        return {proxy.strip() for proxy in self.TRUSTED_PROXIES.split(",") if proxy.strip()}

    @field_validator("POSTGRES_DB")
    @classmethod
    def validate_compose_postgres(cls, postgres_db: str | None, info: ValidationInfo) -> str | None:
        postgres_user = info.data.get("POSTGRES_USER")
        postgres_password_value = info.data.get("POSTGRES_PASSWORD")
        compose_postgres = {
            "POSTGRES_USER": postgres_user,
            "POSTGRES_PASSWORD": postgres_password_value,
            "POSTGRES_DB": postgres_db,
        }
        supplied = {name for name, value in compose_postgres.items() if value is not None}
        if supplied and len(supplied) != len(compose_postgres):
            raise ValueError("POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB must be set together")

        if supplied:
            postgres_user = str(postgres_user or "")
            postgres_password = (
                postgres_password_value.get_secret_value() if isinstance(postgres_password_value, SecretStr) else ""
            )
            postgres_db = postgres_db or ""
            if not postgres_user.strip() or not postgres_password or not postgres_db.strip():
                raise ValueError("POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB cannot be empty")

            try:
                database_url = make_url(str(info.data.get("DATABASE_URL") or ""))
            except (ArgumentError, ValueError) as exc:
                raise ValueError("DATABASE_URL must be a valid PostgreSQL URL when POSTGRES_* is set") from exc

            if database_url.get_backend_name() != "postgresql":
                raise ValueError("DATABASE_URL must use PostgreSQL when POSTGRES_* is set")

            database_values = {
                "POSTGRES_USER": database_url.username,
                "POSTGRES_PASSWORD": database_url.password,
                "POSTGRES_DB": database_url.database,
            }
            compose_values = {
                "POSTGRES_USER": postgres_user,
                "POSTGRES_PASSWORD": postgres_password,
                "POSTGRES_DB": postgres_db,
            }
            mismatched = [name for name, value in compose_values.items() if database_values[name] != value]
            if mismatched:
                raise ValueError(f"{', '.join(mismatched)} must match DATABASE_URL")

        return postgres_db

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        is_production = self.APP_ENV == "production"
        allow_insecure_defaults = self.ALLOW_INSECURE_DEV_DEFAULTS and self.APP_ENV in {"development", "test", "local"}

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
