"""Query / RAG API endpoint."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.schemas import QueryRequest, QueryResponse, SourceChunk
from app.services.gemini import generate_answer
from app.services.hybrid_search import hybrid_search

router = APIRouter()


@router.post("/", response_model=QueryResponse)
async def query_knowledge_base(
    payload: QueryRequest,
    session: AsyncSession = Depends(get_session),
) -> QueryResponse:
    """Hybrid-search the knowledge base and generate a grounded response."""
    # 1. Hybrid retrieval
    t0 = time.perf_counter()
    results = await hybrid_search(
        session,
        query=payload.query,
        top_k=payload.top_k,
        dense_weight=payload.dense_weight,
        sparse_weight=payload.sparse_weight,
    )
    retrieval_ms = (time.perf_counter() - t0) * 1000

    # 2. LLM generation with retrieved context
    context = results[: settings.top_k_context]
    t1 = time.perf_counter()
    answer = await generate_answer(query=payload.query, context_chunks=context)
    generation_ms = (time.perf_counter() - t1) * 1000

    return QueryResponse(
        answer=answer,
        sources=[
            SourceChunk(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_title=r.document_title,
                content=r.content,
                score=round(r.score, 4),
            )
            for r in results
        ],
        query=payload.query,
        model=settings.gemini_chat_model,
        retrieval_ms=round(retrieval_ms, 2),
        generation_ms=round(generation_ms, 2),
    )
