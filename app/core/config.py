from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://telo:telo_dev@db:5432/telo_venue_assistant"
    database_url_sync: str = "postgresql://telo:telo_dev@db:5432/telo_venue_assistant"

    # Embedding provider
    embedding_provider: str = "openai"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # LLM provider
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""

    # Retrieval
    chunk_size: int = 512
    chunk_overlap: int = 50
    retrieval_top_k: int = 5
    similarity_threshold: float = 0.5
    rrf_k: int = 60

    # App
    app_env: str = "development"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()