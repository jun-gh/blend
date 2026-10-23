"""Query / RAG API endpoint."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import require_site_auth
from app.core.session import get_session_id
from app.models.schemas import QueryRequest, QueryResponse, SourceChunk
from app.security.pii_scrubber import scrub_pii
from app.security.prompt_guard import check_prompt_injection
from app.security.rate_limiter import rate_limit_query
from app.services.gemini import generate_answer, generate_answer_stream
from app.services.hybrid_search import hybrid_search
from app.services.intent import (
    align_citations_with_answer,
    is_conversational_query,
    is_no_context_answer,
)

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_site_auth), Depends(rate_limit_query)])


@router.post("/", response_model=QueryResponse)
async def query_knowledge_base(
    payload: QueryRequest,
    session: AsyncSession = Depends(get_session),
    session_id: str = Depends(get_session_id),
) -> QueryResponse:
    """Hybrid-search the knowledge base and generate a grounded response."""
    # 1. Prompt Injection Guard (< 0.5ms Instant Quarantine)
    if settings.enable_prompt_guard:
        guard_res = check_prompt_injection(payload.query)
        if guard_res.is_quarantined:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Security Guardrail: Request quarantined ({guard_res.reason}). "
                    "Please reformulate your question."
                ),
            )

    # 2. PII Redaction Engine
    sanitized_query = payload.query
    token_map = None
    if settings.enable_pii_scrubbing:
        sanitized_query, token_map = scrub_pii(payload.query)

    # 3. Conversational Intent Filter & Hybrid Retrieval
    is_conversational = is_conversational_query(sanitized_query)

    if is_conversational:
        results = []
        retrieval_ms = 0.0
    else:
        active_session_id = payload.session_id or session_id
        t0 = time.perf_counter()
        results = await hybrid_search(
            session,
            query=sanitized_query,
            top_k=payload.top_k,
            dense_weight=payload.dense_weight,
            sparse_weight=payload.sparse_weight,
            session_id=active_session_id,
            min_similarity=settings.similarity_threshold,
        )
        retrieval_ms = (time.perf_counter() - t0) * 1000

    # 4. LLM generation with retrieved context and Output Policy Shield
    context = results[: settings.top_k_context]
    t1 = time.perf_counter()
    try:
        answer = await generate_answer(
            query=sanitized_query,
            context_chunks=context,
            token_map=token_map,
            is_conversational=is_conversational,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response from AI model: {exc}",
        ) from exc
    generation_ms = (time.perf_counter() - t1) * 1000

    # Align and verify citations against the generated answer
    aligned_results = align_citations_with_answer(answer, context)

    return QueryResponse(
        answer=answer,
        sources=[
            SourceChunk(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_title=r.document_title,
                content=r.content,
                score=round(r.similarity if r.similarity > 0 else r.score, 4),
            )
            for r in aligned_results
        ],
        query=payload.query,
        model=settings.gemini_chat_model,
        model_name=settings.chat_model_display_name,
        retrieval_ms=round(retrieval_ms, 2),
        generation_ms=round(generation_ms, 2),
    )


@router.post("/stream")
async def query_knowledge_base_stream(
    payload: QueryRequest,
    session: AsyncSession = Depends(get_session),
    session_id: str = Depends(get_session_id),
) -> StreamingResponse:
    """Hybrid-search the knowledge base and stream a grounded response via Server-Sent Events (SSE).

    Flow:
    1. Instant Quarantining & PII Scrubbing (< 0.5ms).
    2. Hybrid Retrieval with Session Filtering (< 150ms).
    3. 'event: sources' emitted immediately (instant source hydration in UI).
    4. 'event: delta' emitted token-by-token from Gemini.
    5. 'event: done' emitted with latency metrics.
    """
    # 1. Prompt Injection Guard (< 0.5ms Instant Quarantine)
    if settings.enable_prompt_guard:
        guard_res = check_prompt_injection(payload.query)
        if guard_res.is_quarantined:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Security Guardrail: Request quarantined ({guard_res.reason}). "
                    "Please reformulate your question."
                ),
            )

    # 2. PII Redaction Engine
    sanitized_query = payload.query
    token_map = None
    if settings.enable_pii_scrubbing:
        sanitized_query, token_map = scrub_pii(payload.query)

    # 3. Conversational Intent Filter & Hybrid Retrieval
    t0 = time.perf_counter()
    is_conversational = is_conversational_query(sanitized_query)

    if is_conversational:
        results = []
        retrieval_ms = 0.0
    else:
        active_session_id = payload.session_id or session_id
        results = await hybrid_search(
            session,
            query=sanitized_query,
            top_k=payload.top_k,
            dense_weight=payload.dense_weight,
            sparse_weight=payload.sparse_weight,
            session_id=active_session_id,
            min_similarity=settings.similarity_threshold,
        )
        retrieval_ms = (time.perf_counter() - t0) * 1000

    context = results[: settings.top_k_context]

    async def event_generator():
        # Event 1: Instant Source Hydration (immediate emit before generation)
        sources_payload = [
            {
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "document_title": r.document_title,
                "content": r.content,
                "score": round(r.similarity if r.similarity > 0 else r.score, 4),
            }
            for r in results
        ]
        sources_meta = {
            "sources": sources_payload,
            "retrieval_ms": round(retrieval_ms, 2),
            "model": settings.gemini_chat_model,
            "model_name": settings.chat_model_display_name,
        }
        yield f"event: sources\ndata: {json.dumps(sources_meta)}\n\n"

        # Event 2: Stream tokens as generated
        t1 = time.perf_counter()
        full_tokens = []
        try:
            async for token in generate_answer_stream(
                query=sanitized_query,
                context_chunks=context,
                token_map=token_map,
                is_conversational=is_conversational,
            ):
                full_tokens.append(token)
                yield f"event: delta\ndata: {json.dumps({'text': token})}\n\n"
        except Exception as exc:
            log.error("Streaming error: %s", exc)
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"
            return

        generation_ms = (time.perf_counter() - t1) * 1000
        total_ms = (time.perf_counter() - t0) * 1000

        full_answer = "".join(full_tokens)
        clear_sources = is_no_context_answer(full_answer)

        # Align and verify citations against the completed answer
        aligned_results = (
            [] if clear_sources else align_citations_with_answer(full_answer, context)
        )
        aligned_sources_payload = [
            {
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "document_title": r.document_title,
                "content": r.content,
                "score": round(r.similarity if r.similarity > 0 else r.score, 4),
            }
            for r in aligned_results
        ]

        # Emit refined sources event if citations were pruned or cleared
        if len(aligned_sources_payload) != len(sources_payload):
            refined_sources_meta = {
                "sources": aligned_sources_payload,
                "retrieval_ms": round(retrieval_ms, 2),
                "model": settings.gemini_chat_model,
                "model_name": settings.chat_model_display_name,
            }
            yield f"event: sources\ndata: {json.dumps(refined_sources_meta)}\n\n"

        # Event 3: Done with generation and total latency metrics
        done_payload = {
            "generation_ms": round(generation_ms, 2),
            "total_ms": round(total_ms, 2),
            "clear_sources": clear_sources,
            "sources": aligned_sources_payload,
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
