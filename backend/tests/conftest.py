"""Shared test fixtures and global mocks for backend tests."""

from unittest.mock import patch

import pytest

from app.core.config import settings


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
