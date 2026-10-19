"""Embedding generation using the Google GenAI SDK.

Wraps `google-genai` to produce dense vector embeddings for text.
Includes automatic retries for transient rate limit or network errors.
"""

from __future__ import annotations

import asyncio
import logging
import random

import google.generativeai as genai

from app.core.config import settings
from app.services.gemini import (
    BACKOFF_FACTOR,
    INITIAL_BACKOFF,
    MAX_RETRIES,
    is_rate_limit_error,
    is_transient_error,
)

log = logging.getLogger(__name__)

if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)


async def embed_texts(
    texts: list[str], task_type: str = "retrieval_document"
) -> list[list[float]]:
    """Return a list of embeddings with up to 3 retries on transient errors."""
    if not texts:
        return []

    if not settings.gemini_api_key:
        log.warning("GEMINI_API_KEY not configured. Generating zero-vector fallback embeddings.")
        return [[0.0] * settings.embedding_dimensions for _ in texts]

    loop = asyncio.get_event_loop()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await loop.run_in_executor(
                None,
                lambda: genai.embed_content(
                    model=settings.gemini_embed_model,
                    content=texts,
                    task_type=task_type,
                ),
            )
            raw = result["embedding"]
            embeddings: list[list[float]] = raw if isinstance(raw[0], list) else [raw]
            log.debug("Embedded %d text(s) -> dim=%d", len(texts), len(embeddings[0]))
            return embeddings
        except Exception as exc:
            rate_limited = is_rate_limit_error(exc)
            transient = is_transient_error(exc)
            if not (rate_limited or transient) or attempt == MAX_RETRIES:
                log.warning(
                    "Gemini embedding failed after %d attempts (%s). Using fallback.",
                    attempt,
                    exc,
                )
                return [[0.0] * settings.embedding_dimensions for _ in texts]

            backoff = (INITIAL_BACKOFF * (BACKOFF_FACTOR ** (attempt - 1))) + random.uniform(
                0.1, 0.4
            )
            log.warning(
                "Embedding attempt %d/%d failed (%s). Retrying in %.2fs...",
                attempt,
                MAX_RETRIES,
                exc,
                backoff,
            )
            await asyncio.sleep(backoff)

    return [[0.0] * settings.embedding_dimensions for _ in texts]


async def embed_query(query: str) -> list[float]:
    """Return a single embedding vector for a search query."""
    vectors = await embed_texts([query], task_type="retrieval_query")
    return vectors[0]
