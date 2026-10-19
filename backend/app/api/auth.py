"""Authentication and password verification endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.core.security import (
    create_access_token,
    is_auth_required,
    verify_site_password,
)
from app.models.schemas import (
    AuthStatusResponse,
    AuthTokenResponse,
    PasswordVerifyRequest,
)

router = APIRouter()


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status() -> AuthStatusResponse:
    """Return whether password protection is currently enabled and active AI model."""
    return AuthStatusResponse(
        required=is_auth_required(),
        model=settings.gemini_chat_model,
        model_name=settings.chat_model_display_name,
    )


@router.post("/verify", response_model=AuthTokenResponse)
async def verify_password(payload: PasswordVerifyRequest) -> AuthTokenResponse:
    """Verify visitor password and issue a signed session token."""
    if not is_auth_required():
        token, expires_at = create_access_token()
        return AuthTokenResponse(token=token, expires_at=expires_at)

    if not verify_site_password(payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect site password.",
        )

    token, expires_at = create_access_token()
    return AuthTokenResponse(token=token, expires_at=expires_at)
