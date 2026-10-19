"""System and model configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import ModelConfigResponse

router = APIRouter()


@router.get("/model", response_model=ModelConfigResponse)
async def get_model_config() -> ModelConfigResponse:
    """Return the active AI model configuration loaded from the environment."""
    return ModelConfigResponse(
        model=settings.gemini_chat_model,
        model_name=settings.chat_model_display_name,
        embed_model=settings.gemini_embed_model,
    )
