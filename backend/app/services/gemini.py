"""Gemini chat generation service.

Builds a grounded prompt from retrieved chunks and calls the Gemini API
to generate a final answer with automatic retries and robust error handling.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

import google.generativeai as genai
from fastapi import HTTPException, status

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.hybrid_search import SearchResult

log = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_FACTOR = 2.0

if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

_SYSTEM_PROMPT = """\
You are Blend, an intelligent research assistant that answers questions strictly
based on the provided context documents. Follow these rules:

1. Answer ONLY using information found in the context below.
2. If the context does not contain enough information, state that clearly.
3. Cite your sources using [Doc: <title>] inline notation.
4. Be concise, accurate, and helpful.
"""


def is_rate_limit_error(exc: Exception) -> bool:
    """Check if exception represents a rate-limit or quota-exceeded error."""
    exc_type = type(exc).__name__
    if exc_type in ("ResourceExhausted", "TooManyRequests"):
        return True
    msg = str(exc).lower()
    return any(
        k in msg
        for k in (
            "429",
            "quota",
            "resource_exhausted",
            "rate limit",
            "resource has been exhausted",
            "queries per minute",
        )
    )


def is_transient_error(exc: Exception) -> bool:
    """Check if exception represents a retryable transient error (500, 503, 504, timeout)."""
    exc_type = type(exc).__name__
    if exc_type in (
        "ServiceUnavailable",
        "InternalServerError",
        "DeadlineExceeded",
        "GatewayTimeout",
    ):
        return True
    msg = str(exc).lower()
    return any(
        k in msg
        for k in (
            "503",
            "504",
            "500",
            "temporarily unavailable",
            "timeout",
            "deadline exceeded",
            "connection reset",
        )
    )


def raise_clean_gemini_error(
    exc: Exception, model_name: str, retried: bool = False
) -> None:
    """Translate raw Gemini API errors into clear, human-readable HTTPExceptions."""
    retry_note = f" (retried {MAX_RETRIES} times)" if retried else ""
    msg = str(exc)

    if is_rate_limit_error(exc):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Gemini model limit exceeded for '{model_name}'{retry_note}. "
                "The rate limit or quota has been reached. Please wait a few moments "
                "before trying again."
            ),
        )

    lower_msg = msg.lower()
    if any(k in lower_msg for k in ("api_key", "permission", "unauthenticated")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unauthorized Gemini API key. Please check your GEMINI_API_KEY.",
        )

    if any(k in lower_msg for k in ("not found", "is not supported")):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' was not found or is unsupported by Google Gemini.",
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Gemini API error{retry_note}: {msg}",
    )


async def generate_answer(
    query: str,
    context_chunks: list[SearchResult],
    model_name: str | None = None,
) -> str:
    """Generate a grounded answer using Gemini with up to 3 retries on transient errors."""
    if not settings.gemini_api_key:
        return (
            "GEMINI_API_KEY is not configured. Here are the retrieved source chunks:\n\n"
            + _build_context(context_chunks)
        )

    model_name = model_name or settings.gemini_chat_model
    context_block = _build_context(context_chunks)

    prompt = (
        f"Context:\n{context_block}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=_SYSTEM_PROMPT,
    )

    loop = asyncio.get_event_loop()
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(
                "Generating answer with '%s' (attempt %d/%d)",
                model_name,
                attempt,
                MAX_RETRIES,
            )
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(prompt),
            )
            return response.text.strip()
        except Exception as exc:
            last_exc = exc
            rate_limited = is_rate_limit_error(exc)
            transient = is_transient_error(exc)

            if not (rate_limited or transient):
                log.error("Non-retryable error during generation: %s", exc)
                raise_clean_gemini_error(exc, model_name)

            if attempt < MAX_RETRIES:
                backoff = (INITIAL_BACKOFF * (BACKOFF_FACTOR ** (attempt - 1))) + random.uniform(
                    0.1, 0.4
                )
                log.warning(
                    "Gemini generation attempt %d/%d failed with %s (%s). Retrying in %.2fs...",
                    attempt,
                    MAX_RETRIES,
                    type(exc).__name__,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
            else:
                log.error("Gemini generation failed after %d attempts: %s", MAX_RETRIES, exc)

    if last_exc:
        raise_clean_gemini_error(last_exc, model_name, retried=True)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to generate answer from Gemini model.",
    )


def _build_context(chunks: list[SearchResult]) -> str:
    """Format chunks into a numbered context block."""
    if not chunks:
        return "No relevant context found."
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[{i}] Document: {chunk.document_title}\n"
            f"---\n{chunk.content}\n"
        )
    return "\n".join(parts)
