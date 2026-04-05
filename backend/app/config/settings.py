from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "MuseAI"
    APP_ENV: str = "development"
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

    # CORS settings
    CORS_ORIGINS: str = "*"  # Comma-separated list or "*"
    CORS_ALLOW_CREDENTIALS: bool = True

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_FORMAT: str = "json"  # "json" or "text"

    @field_validator("EMBEDDING_DIMS")
    @classmethod
    def validate_embedding_dims(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("EMBEDDING_DIMS must be positive")
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        is_production = self.APP_ENV == "production"

        if is_production:
            if not self.JWT_SECRET:
                raise ValueError("JWT_SECRET must be set in production")
            if len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if not self.LLM_API_KEY:
                raise ValueError("LLM_API_KEY must be set in production")

        # Development defaults
        if not self.JWT_SECRET:
            self.JWT_SECRET = "dev-secret-do-not-use-in-production"
        if not self.LLM_API_KEY:
            self.LLM_API_KEY = "dev-key-do-not-use-in-production"

        return self

    def get_cors_origins(self) -> list[str]:
        """Parse CORS_ORIGINS setting into a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


def get_settings() -> Settings:
    return Settings()
