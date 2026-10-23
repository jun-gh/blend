"""Shared test fixtures and global mocks for backend tests."""

import os
from unittest.mock import patch

import pytest

# Ensure unit tests execute against an isolated test DB to avoid wiping or polluting
# the active development/production PostgreSQL database
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_blend.db")

from app.core.config import get_settings, settings  # noqa: E402

get_settings.cache_clear()



@pytest.fixture(autouse=True)
def mock_embedding_service():
    """Mock embed_texts globally during tests to prevent external Gemini API calls."""
    with (
        patch(
            "app.services.embedding.embed_texts",
            side_effect=lambda texts, **kwargs: (
                [[0.0] * settings.embedding_dimensions for _ in texts]
            ),
        ),
        patch(
            "app.services.ingestion.embed_texts",
            side_effect=lambda texts, **kwargs: (
                [[0.0] * settings.embedding_dimensions for _ in texts]
            ),
        ),
    ):
        yield
