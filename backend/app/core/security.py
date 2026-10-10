"""Minimal security utilities.

For now this module provides a simple API-key dependency that can be wired
into FastAPI routes.  Extend with OAuth2 / JWT as the project grows.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """Dependency: validates the X-API-Key header.

    If BLEND_API_KEY env-var is not set, the endpoint is open (dev mode).
    """
    expected: str = getattr(settings, "blend_api_key", "")
    if not expected:
        return "open"  # Dev mode – no key configured
    if api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return api_key
