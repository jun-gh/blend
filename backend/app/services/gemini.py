"""Gemini chat generation service.

Builds a grounded prompt from retrieved chunks and calls the Gemini API
to generate a final answer.
"""

from __future__ import annotations

import asyncio
import logging

import google.generativeai as genai

from app.core.config import settings
from app.services.hybrid_search import SearchResult

log = logging.getLogger(__name__)

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


async def generate_answer(
    query: str,
    context_chunks: list[SearchResult],
    model_name: str | None = None,
) -> str:
    """Generate a grounded answer using Gemini."""
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
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(prompt),
    )
    return response.text.strip()


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
