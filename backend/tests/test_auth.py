"""Unit tests for site password protection and session token lifecycle."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.security import (
    create_access_token,
    verify_access_token,
    verify_site_password,
)
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_password_verification():
    original_pwd = settings.site_password
    try:
        settings.site_password = "my-secure-password"
        assert verify_site_password("my-secure-password") is True
        assert verify_site_password("wrong-password") is False
    finally:
        settings.site_password = original_pwd


def test_token_invalidation_on_password_change():
    original_pwd = settings.site_password
    try:
        settings.site_password = "password-v1"
        token, _ = create_access_token()
        assert verify_access_token(token) is True

        # Rotate password
        settings.site_password = "password-v2"
        # Old token must now be invalid
        assert verify_access_token(token) is False
    finally:
        settings.site_password = original_pwd


@pytest.mark.anyio
async def test_auth_status_and_verification_flow():
    original_pwd = settings.site_password
    try:
        settings.site_password = "production-passcode"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 1. Status check
            status_res = await client.get("/api/auth/status")
            assert status_res.status_code == 200
            assert status_res.json()["required"] is True

            # 2. Verify with wrong password
            wrong_res = await client.post(
                "/api/auth/verify", json={"password": "wrong"}
            )
            assert wrong_res.status_code == 401

            # 3. Verify with correct password
            correct_res = await client.post(
                "/api/auth/verify", json={"password": "production-passcode"}
            )
            assert correct_res.status_code == 200
            token_data = correct_res.json()
            assert "token" in token_data
            token = token_data["token"]

            # 4. Access protected endpoint without token -> 401
            no_auth_res = await client.get("/api/documents/")
            assert no_auth_res.status_code == 401

            # 5. Access protected endpoint with valid token -> 200
            authed_res = await client.get(
                "/api/documents/",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert authed_res.status_code == 200

            # 6. Rotate password
            settings.site_password = "new-passcode"

            # 7. Old token is now rejected
            revoked_res = await client.get(
                "/api/documents/",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert revoked_res.status_code == 401
    finally:
        settings.site_password = original_pwd
