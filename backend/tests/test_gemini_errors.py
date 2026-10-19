"""Unit tests for Gemini error classification, retries, and HTTP error translation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.gemini import (
    MAX_RETRIES,
    generate_answer,
    is_rate_limit_error,
    is_transient_error,
    raise_clean_gemini_error,
)
from app.services.hybrid_search import SearchResult


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_is_rate_limit_error_detects_classes_and_messages():
    class ResourceExhausted(Exception):  # noqa: N818
        pass

    class TooManyRequests(Exception):  # noqa: N818
        pass

    assert is_rate_limit_error(ResourceExhausted("exhausted")) is True
    assert is_rate_limit_error(TooManyRequests("too many")) is True
    assert is_rate_limit_error(Exception("429 Resource has been exhausted")) is True
    assert is_rate_limit_error(Exception("Quota exceeded for quota metric")) is True
    assert is_rate_limit_error(Exception("Rate limit reached for requests per minute")) is True

    # Non-rate-limit errors
    assert is_rate_limit_error(ValueError("Invalid syntax")) is False
    assert is_rate_limit_error(Exception("500 Internal error")) is False


def test_is_transient_error_detects_classes_and_messages():
    class ServiceUnavailable(Exception):  # noqa: N818
        pass

    class DeadlineExceeded(Exception):  # noqa: N818
        pass

    assert is_transient_error(ServiceUnavailable("server busy")) is True
    assert is_transient_error(DeadlineExceeded("timeout")) is True
    assert is_transient_error(Exception("503 Service Unavailable")) is True
    assert is_transient_error(Exception("504 Gateway Timeout")) is True
    assert is_transient_error(Exception("500 Internal Server Error")) is True
    assert is_transient_error(Exception("Connection reset by peer")) is True

    # Non-transient errors
    assert is_transient_error(ValueError("Bad value")) is False
    assert is_transient_error(Exception("401 Unauthorized")) is False


def test_raise_clean_gemini_error_rate_limit():
    with pytest.raises(HTTPException) as exc_info:
        raise_clean_gemini_error(
            Exception("429 Resource has been exhausted"),
            model_name="gemini-2.0-flash",
            retried=True,
        )
    assert exc_info.value.status_code == 429
    assert "Gemini model limit exceeded for 'gemini-2.0-flash' (retried 3 times)" in (
        exc_info.value.detail
    )


def test_raise_clean_gemini_error_auth():
    with pytest.raises(HTTPException) as exc_info:
        raise_clean_gemini_error(
            Exception("API_KEY_INVALID: permission denied"),
            model_name="gemini-2.0-flash",
        )
    assert exc_info.value.status_code == 401
    assert "Invalid or unauthorized Gemini API key" in exc_info.value.detail


def test_raise_clean_gemini_error_not_found():
    with pytest.raises(HTTPException) as exc_info:
        raise_clean_gemini_error(
            Exception("Model models/custom-x was not found"),
            model_name="custom-x",
        )
    assert exc_info.value.status_code == 404
    assert "Model 'custom-x' was not found" in exc_info.value.detail


@pytest.mark.anyio
async def test_generate_answer_succeeds_on_retry():
    chunks = [
        SearchResult(
            chunk_id=1,
            document_id=1,
            document_title="Blend Architecture",
            content="Blend uses hybrid search.",
        )
    ]

    mock_resp = MagicMock()
    mock_resp.text = "Blend is a hybrid search system."

    # Fail twice with 503, succeed on 3rd attempt
    side_effects = [
        Exception("503 Service Unavailable"),
        Exception("503 Service Unavailable"),
        mock_resp,
    ]

    with (
        patch("app.services.gemini.settings.gemini_api_key", "test-key"),
        patch("google.generativeai.GenerativeModel") as mock_model_cls,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = side_effects
        mock_model_cls.return_value = mock_instance

        answer = await generate_answer("What is Blend?", chunks)

        assert answer == "Blend is a hybrid search system."
        assert mock_instance.generate_content.call_count == 3
        assert mock_sleep.call_count == 2


@pytest.mark.anyio
async def test_generate_answer_exhausts_max_retries():
    chunks = [
        SearchResult(
            chunk_id=1,
            document_id=1,
            document_title="Doc",
            content="Content",
        )
    ]

    with (
        patch("app.services.gemini.settings.gemini_api_key", "test-key"),
        patch("google.generativeai.GenerativeModel") as mock_model_cls,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = Exception("429 Resource has been exhausted")
        mock_model_cls.return_value = mock_instance

        with pytest.raises(HTTPException) as exc_info:
            await generate_answer("Test query", chunks)

        assert exc_info.value.status_code == 429
        assert f"retried {MAX_RETRIES} times" in exc_info.value.detail
        assert mock_instance.generate_content.call_count == MAX_RETRIES
        assert mock_sleep.call_count == MAX_RETRIES - 1
