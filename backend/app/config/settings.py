from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "MuseAI"
    APP_ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    REDIS_URL: str = "redis://localhost:6379"
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    JWT_SECRET: str = "test-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    LLM_PROVIDER: str = "openai"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = "test-key"
    LLM_MODEL: str = "gpt-4o-mini"

    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBEDDING_OLLAMA_MODEL: str = "nomic-embed-text"

    ELASTICSEARCH_INDEX: str = "museai_chunks_v1"
    EMBEDDING_DIMS: int = 768

    @field_validator("EMBEDDING_DIMS")
    @classmethod
    def validate_embedding_dims(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("EMBEDDING_DIMS must be positive")
        return v


def get_settings() -> Settings:
    return Settings()
