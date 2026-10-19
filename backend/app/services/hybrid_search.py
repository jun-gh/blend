"""Hybrid search engine combining dense (vector) and sparse (FTS) retrieval.

Algorithm:
1. Dense retrieval  - cosine similarity between query embedding and chunk embeddings.
2. Sparse retrieval - SQLite FTS5 BM25 score (or Postgres tsvector rank / LIKE fallback).
3. Reciprocal Rank Fusion (RRF) - normalize and merge both ranked lists.

Scoring formula (RRF):
    score(d) = dense_weight / (k + dense_rank) + sparse_weight / (k + sparse_rank)
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.session import get_session_cutoff
from app.services.embedding import embed_query

log = logging.getLogger(__name__)

_RRF_K = 60  # Standard RRF constant


@dataclass
class SearchResult:
    chunk_id: int
    document_id: int
    document_title: str
    content: str
    dense_rank: int = 0
    sparse_rank: int = 0
    score: float = 0.0


async def hybrid_search(
    session: AsyncSession,
    query: str,
    top_k: int | None = None,
    dense_weight: float | None = None,
    sparse_weight: float | None = None,
    session_id: str | None = None,
) -> list[SearchResult]:
    """Perform hybrid retrieval and return top_k ranked results."""
    top_k = top_k or settings.top_k_retrieval
    dw = dense_weight if dense_weight is not None else settings.dense_weight
    sw = sparse_weight if sparse_weight is not None else settings.sparse_weight

    # Normalize weights
    total = dw + sw
    if total > 0:
        dw, sw = dw / total, sw / total
    else:
        dw, sw = 0.5, 0.5

    query_vec = await embed_query(query)

    dense_results = await _dense_search(session, query_vec, top_k, session_id=session_id)
    sparse_results = await _sparse_search(session, query, top_k, session_id=session_id)

    merged = _rrf_merge(dense_results, sparse_results, dw, sw, top_k)
    return merged


async def _dense_search(
    session: AsyncSession,
    query_vec: list[float],
    top_k: int,
    session_id: str | None = None,
) -> list[dict]:
    """Fetch all chunk embeddings and rank by cosine similarity."""
    cutoff = get_session_cutoff()
    params: dict = {"cutoff": cutoff}
    where_clauses = ["c.embedding_json IS NOT NULL", "d.created_at >= :cutoff"]
    if session_id:
        where_clauses.append("d.session_id = :session_id")
        params["session_id"] = session_id

    where_sql = " AND ".join(where_clauses)
    query_sql = f"""
        SELECT c.id, c.document_id, c.content, c.embedding_json, d.title
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE {where_sql}
    """
    rows = await session.execute(text(query_sql), params)
    results = []
    for row in rows:
        if not row.embedding_json:
            continue
        vec = json.loads(row.embedding_json)
        sim = _cosine_similarity(query_vec, vec)
        results.append(
            {
                "chunk_id": row.id,
                "document_id": row.document_id,
                "document_title": row.title,
                "content": row.content,
                "score": sim,
            }
        )
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


async def _sparse_search(
    session: AsyncSession,
    query: str,
    top_k: int,
    session_id: str | None = None,
) -> list[dict]:
    """SQLite FTS5 full-text search with fallback to LIKE search."""
    cutoff = get_session_cutoff()
    is_sqlite = settings.database_url.startswith("sqlite")

    if is_sqlite:
        try:
            clean_query = "".join(c for c in query if c.isalnum() or c.isspace()).strip()
            if not clean_query:
                clean_query = query.strip()

            params: dict = {"q": clean_query, "k": top_k, "cutoff": cutoff}
            where_sql = "chunks_fts MATCH :q AND d.created_at >= :cutoff"
            if session_id:
                where_sql += " AND d.session_id = :session_id"
                params["session_id"] = session_id

            rows = await session.execute(
                text(
                    f"""
                    SELECT c.id, c.document_id, c.content, d.title,
                           bm25(chunks_fts) AS bm25_score
                    FROM chunks_fts
                    JOIN chunks c ON c.id = chunks_fts.rowid
                    JOIN documents d ON d.id = c.document_id
                    WHERE {where_sql}
                    ORDER BY bm25_score
                    LIMIT :k
                    """
                ),
                params,
            )
            return [
                {
                    "chunk_id": row.id,
                    "document_id": row.document_id,
                    "document_title": row.title,
                    "content": row.content,
                    "score": abs(float(row.bm25_score)),
                }
                for row in rows
            ]
        except Exception as exc:  # noqa: BLE001
            log.warning("FTS search failed: %s", exc)
            await session.rollback()

    # Fallback / PostgreSQL search using LIKE / ILIKE
    try:
        params = {"q": f"%{query}%", "k": top_k, "cutoff": cutoff}
        where_sql = "c.content ILIKE :q AND d.created_at >= :cutoff"
        if session_id:
            where_sql += " AND d.session_id = :session_id"
            params["session_id"] = session_id

        rows = await session.execute(
            text(
                f"""
                SELECT c.id, c.document_id, c.content, d.title, 1.0 AS score
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE {where_sql}
                LIMIT :k
                """
            ),
            params,
        )
        return [
            {
                "chunk_id": row.id,
                "document_id": row.document_id,
                "document_title": row.title,
                "content": row.content,
                "score": float(row.score),
            }
            for row in rows
        ]
    except Exception:
        # SQLite doesn't have ILIKE, use LIKE
        await session.rollback()
        params = {"q": f"%{query}%", "k": top_k, "cutoff": cutoff}
        where_sql = "c.content LIKE :q AND d.created_at >= :cutoff"
        if session_id:
            where_sql += " AND d.session_id = :session_id"
            params["session_id"] = session_id

        rows = await session.execute(
            text(
                f"""
                SELECT c.id, c.document_id, c.content, d.title, 1.0 AS score
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE {where_sql}
                LIMIT :k
                """
            ),
            params,
        )
        return [
            {
                "chunk_id": row.id,
                "document_id": row.document_id,
                "document_title": row.title,
                "content": row.content,
                "score": float(row.score),
            }
            for row in rows
        ]


def _rrf_merge(
    dense: list[dict],
    sparse: list[dict],
    dense_weight: float,
    sparse_weight: float,
    top_k: int,
) -> list[SearchResult]:
    """Merge ranked lists using Reciprocal Rank Fusion."""
    registry: dict[int, SearchResult] = {}

    for rank, d in enumerate(dense, start=1):
        cid = d["chunk_id"]
        if cid not in registry:
            registry[cid] = SearchResult(
                chunk_id=cid,
                document_id=d["document_id"],
                document_title=d["document_title"],
                content=d["content"],
            )
        registry[cid].dense_rank = rank
        registry[cid].score += dense_weight / (_RRF_K + rank)

    for rank, s in enumerate(sparse, start=1):
        cid = s["chunk_id"]
        if cid not in registry:
            registry[cid] = SearchResult(
                chunk_id=cid,
                document_id=s["document_id"],
                document_title=s["document_title"],
                content=s["content"],
            )
        registry[cid].sparse_rank = rank
        registry[cid].score += sparse_weight / (_RRF_K + rank)

    ranked = sorted(registry.values(), key=lambda r: r.score, reverse=True)
    return ranked[:top_k]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if len(a) != len(b) or not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
