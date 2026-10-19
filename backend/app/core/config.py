"""Application configuration via Pydantic v2 BaseSettings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def format_model_name(model_id: str) -> str:
    """Format model identifier (e.g. 'models/gemini-2.0-flash') into human-readable title."""
    if not model_id:
        return "Unknown Model"
    clean = model_id.removeprefix("models/").strip()
    parts = clean.split("-")
    capitalized_parts: list[str] = []
    for part in parts:
        lower = part.lower()
        if lower == "gemini":
            capitalized_parts.append("Gemini")
        elif lower == "flash":
            capitalized_parts.append("Flash")
        elif lower == "pro":
            capitalized_parts.append("Pro")
        elif lower == "exp":
            capitalized_parts.append("Exp")
        elif any(c.isdigit() for c in part):
            capitalized_parts.append(part.upper() if len(part) <= 3 else part)
        else:
            capitalized_parts.append(part.capitalize())
    return " ".join(capitalized_parts)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "infra/app.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Blend"
    debug: bool = False
    cors_origins: list[str] = ["*"]
    site_password: str | None = Field(default="", alias="SITE_PASSWORD")
    token_expiry_days: int = 7
    session_expiry_days: int = Field(default=7, alias="SESSION_EXPIRY_DAYS")
    max_documents_per_session: int = Field(default=10, alias="MAX_DOCUMENTS_PER_SESSION")

    # Database
    database_url: str = "sqlite+aiosqlite:///./blend.db"
    # Set to a Neon Postgres URL in production:
    # database_url: str = "postgresql+asyncpg://user:pass@host/dbname"

    # Google Gemini
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_embed_model: str = Field(default="models/text-embedding-004", alias="GEMINI_EMBED_MODEL")
    gemini_chat_model: str = Field(default="models/gemini-2.0-flash", alias="GEMINI_CHAT_MODEL")
    embedding_dimensions: int = 768

    @property
    def chat_model_display_name(self) -> str:
        """Human-readable display name for the configured Gemini chat model."""
        return format_model_name(self.gemini_chat_model)

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
