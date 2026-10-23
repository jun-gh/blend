"""Application configuration via Pydantic v2 BaseSettings."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROOT_ENV = _REPO_ROOT / ".env"
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"


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
        env_file=(_ROOT_ENV, ".env", "../.env", _BACKEND_ENV, "infra/app.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Blend"
    debug: bool = False
    cors_origins: list[str] = ["*"]
    site_password: str | None = Field(default="", alias="SITE_PASSWORD")
    blend_api_key: str | None = Field(default="", alias="BLEND_API_KEY")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Support JSON arrays, comma-separated lists, and single domain URLs."""
        if isinstance(v, str):
            clean = v.strip()
            if not clean:
                return ["*"]
            if clean.startswith("[") and clean.endswith("]"):
                import json
                try:
                    return json.loads(clean)
                except Exception:
                    pass
            return [origin.strip() for origin in clean.split(",") if origin.strip()]
        if isinstance(v, list | tuple):
            return list(v)
        return ["*"]

    token_expiry_days: int = 7
    session_expiry_days: int = Field(default=7, alias="SESSION_EXPIRY_DAYS")
    max_documents_per_session: int = Field(default=10, alias="MAX_DOCUMENTS_PER_SESSION")

    # Security & Guardrails
    enable_rate_limiting: bool = Field(default=True, alias="ENABLE_RATE_LIMITING")
    rate_limit_query_per_min: int = Field(default=30, alias="RATE_LIMIT_QUERY_PER_MIN")
    rate_limit_ingest_per_min: int = Field(default=15, alias="RATE_LIMIT_INGEST_PER_MIN")
    rate_limit_auth_per_min: int = Field(default=10, alias="RATE_LIMIT_AUTH_PER_MIN")
    enable_pii_scrubbing: bool = Field(default=True, alias="ENABLE_PII_SCRUBBING")
    enable_prompt_guard: bool = Field(default=True, alias="ENABLE_PROMPT_GUARD")
    enable_output_shield: bool = Field(default=True, alias="ENABLE_OUTPUT_SHIELD")

    # Database
    database_url: str = "postgresql+asyncpg://blend:blend_local_password@localhost:5432/blend"


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
    top_k_context: int = 5      # Docs sent to LLM context window (maximum citations)
    similarity_threshold: float = Field(default=0.50, alias="SIMILARITY_THRESHOLD")
    relative_score_threshold: float = Field(default=0.80, alias="RELATIVE_SCORE_THRESHOLD")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
