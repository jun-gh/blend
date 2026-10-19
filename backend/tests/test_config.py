"""Unit tests for dynamic model configuration."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import format_model_name, settings
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_format_model_name():
    assert format_model_name("models/gemini-2.0-flash") == "Gemini 2.0 Flash"
    assert format_model_name("models/gemini-1.5-pro") == "Gemini 1.5 Pro"
    assert format_model_name("gemini-2.0-flash") == "Gemini 2.0 Flash"
    assert format_model_name("models/gemini-1.5-flash-8b") == "Gemini 1.5 Flash 8B"
    assert format_model_name("") == "Unknown Model"


@pytest.mark.anyio
async def test_get_model_config_endpoint():
    original_model = settings.gemini_chat_model
    try:
        settings.gemini_chat_model = "models/gemini-2.5-flash"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.get("/api/config/model")
            assert res.status_code == 200
            data = res.json()
            assert data["model"] == "models/gemini-2.5-flash"
            assert data["model_name"] == "Gemini 2.5 Flash"
            assert "embed_model" in data
    finally:
        settings.gemini_chat_model = original_model
