"""Application configuration via Pydantic v2 BaseSettings."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Blend"
    debug: bool = False
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database
    database_url: str = "sqlite+aiosqlite:///./blend.db"
    # Set to a Neon Postgres URL in production:
    # database_url: str = "postgresql+asyncpg://user:pass@host/dbname"

    # Google Gemini
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_embed_model: str = "models/gemini-embedding-2"
    gemini_chat_model: str = "models/gemini-3.8-flash"
    embedding_dimensions: int = 3072

    # Hybrid Search weights (must sum to 1.0)
    dense_weight: float = 0.6   # Weight for vector/dense score
    sparse_weight: float = 0.4  # Weight for BM25/FTS score

    # Retrieval
    top_k_retrieval: int = 10   # Docs fetched before re-ranking
    top_k_context: int = 5      # Docs sent to LLM context window


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
