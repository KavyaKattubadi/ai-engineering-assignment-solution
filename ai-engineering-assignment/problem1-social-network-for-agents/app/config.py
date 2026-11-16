from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agents_network"
    redis_url: str = "redis://localhost:6379/0"

    # Embedding model (OpenAI or compatible)
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Routing thresholds
    vector_top_k: int = 50
    rerank_threshold: float = 0.75

    # Security
    webhook_timeout_seconds: float = 5.0

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()