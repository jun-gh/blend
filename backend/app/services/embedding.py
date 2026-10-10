"""Embedding generation using the Google GenAI SDK.

Wraps `google-genai` to produce dense vector embeddings for text.
Used for both document ingestion and query-time embedding.
"""

from __future__ import annotations

import logging
from typing import List

import google.generativeai as genai

from app.core.config import settings

log = logging.getLogger(__name__)

if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)


async def embed_texts(texts: List[str], task_type: str = "retrieval_document") -> List[List[float]]:
    """Return a list of embeddings, one per input text.

    Args:
        texts: List of strings to embed.
        task_type: One of 'retrieval_document' | 'retrieval_query' | 'semantic_similarity'.

    Returns:
        List of float vectors (one per text).
    """
    if not texts:
        return []

    if not settings.gemini_api_key:
        log.warning("GEMINI_API_KEY not configured. Generating zero-vector fallback embeddings.")
        return [[0.0] * settings.embedding_dimensions for _ in texts]

    # The SDK batch API is synchronous – run in thread pool to avoid blocking the event loop
    import asyncio

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(
                model=settings.gemini_embed_model,
                content=texts,
                task_type=task_type,
            ),
        )
        embeddings: List[List[float]] = result["embedding"] if isinstance(result["embedding"][0], list) else [result["embedding"]]
        log.debug("Embedded %d text(s) → dim=%d", len(texts), len(embeddings[0]))
        return embeddings
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini embedding call failed (%s). Returning zero-vector fallback.", exc)
        return [[0.0] * settings.embedding_dimensions for _ in texts]


async def embed_query(query: str) -> List[float]:
    """Return a single embedding vector for a search query."""
    vectors = await embed_texts([query], task_type="retrieval_query")
    return vectors[0]
