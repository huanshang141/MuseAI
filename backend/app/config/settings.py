from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str
    APP_ENV: str
    DEBUG: bool

    DATABASE_URL: str
    REDIS_URL: str
    ELASTICSEARCH_URL: str

    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int

    LLM_PROVIDER: str
    LLM_BASE_URL: str
    LLM_API_KEY: str
    LLM_MODEL: str

    EMBEDDING_PROVIDER: str
    EMBEDDING_OLLAMA_BASE_URL: str
    EMBEDDING_OLLAMA_MODEL: str

    ELASTICSEARCH_INDEX: str
    EMBEDDING_DIMS: int

    @field_validator("EMBEDDING_DIMS")
    @classmethod
    def validate_embedding_dims(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("EMBEDDING_DIMS must be positive")
        return v


def get_settings() -> Settings:
    return Settings()
