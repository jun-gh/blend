"""Site security and authentication utilities.

Provides password verification and HMAC-SHA256 session tokens.
Tokens are signed directly with the configured SITE_PASSWORD so that
updating the password immediately invalidates all previously issued tokens.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time

from fastapi import Header, HTTPException, status

from app.core.config import settings

log = logging.getLogger(__name__)


def is_auth_required() -> bool:
    """Return True if SITE_PASSWORD is configured and non-empty."""
    return bool(settings.site_password and settings.site_password.strip())


def verify_site_password(password: str) -> bool:
    """Validate visitor password against settings.site_password using constant-time comparison."""
    if not is_auth_required():
        return True
    return secrets.compare_digest(password.strip(), settings.site_password.strip())


def create_access_token() -> tuple[str, int]:
    """Generate an HMAC-SHA256 signed session token and return (token, expires_at)."""
    current_time = int(time.time())
    expires_at = current_time + (settings.token_expiry_days * 86400)
    payload = f"v1:{expires_at}"
    key = settings.site_password.strip().encode("utf-8")
    signature = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{payload}:{signature}"
    return token, expires_at


def verify_access_token(token: str) -> bool:
    """Verify session token signature and expiration against the current SITE_PASSWORD."""
    if not is_auth_required():
        return True
    if not token or not token.strip():
        return False

    parts = token.strip().split(":")
    if len(parts) != 3:
        return False

    version, expires_at_str, signature = parts
    if version != "v1":
        return False

    try:
        expires_at = int(expires_at_str)
    except ValueError:
        return False

    if expires_at <= int(time.time()):
        log.debug("Session token has expired.")
        return False

    payload = f"{version}:{expires_at_str}"
    key = settings.site_password.strip().encode("utf-8")
    expected_sig = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return secrets.compare_digest(signature, expected_sig)


async def require_site_auth(authorization: str | None = Header(None)) -> bool:
    """FastAPI dependency to protect endpoints with the site access token."""
    if not is_auth_required():
        return True

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        # Fallback if raw token was passed directly
        token = authorization.strip()

    if not verify_access_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please enter the site password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
