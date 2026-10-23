"""Hybrid search engine combining dense (vector) and sparse (FTS) retrieval.

Algorithm:
1. Dense retrieval  - cosine similarity between query embedding and chunk embeddings.
2. Sparse retrieval - SQLite FTS5 BM25 score with stopword filtering & query expansion.
3. Contextual Header Anchoring - evaluates Chunk 0 metadata for contact, location, author.
4. Reciprocal Rank Fusion (RRF) - normalize and merge ranked lists with score drop-off.

Scoring formula (RRF):
    score(d) = dense_weight / (k + dense_rank) + sparse_weight / (k + sparse_rank)
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.session import get_session_cutoff
from app.services.embedding import embed_query

log = logging.getLogger(__name__)

_RRF_K = 60  # Standard RRF constant

STOP_WORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren't",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "can't",
    "cannot",
    "could",
    "couldn't",
    "did",
    "didn't",
    "do",
    "does",
    "doesn't",
    "doing",
    "don't",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "hadn't",
    "has",
    "hasn't",
    "have",
    "haven't",
    "having",
    "he",
    "he'd",
    "he'll",
    "he's",
    "her",
    "here",
    "here's",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "how's",
    "i",
    "i'd",
    "i'll",
    "i'm",
    "i've",
    "if",
    "in",
    "into",
    "is",
    "isn't",
    "it",
    "it's",
    "its",
    "itself",
    "let's",
    "me",
    "more",
    "most",
    "mustn't",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "ought",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "shan't",
    "she",
    "she'd",
    "she'll",
    "she's",
    "should",
    "shouldn't",
    "so",
    "some",
    "such",
    "than",
    "that",
    "that's",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "there's",
    "these",
    "they",
    "they'd",
    "they'll",
    "they're",
    "they've",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "wasn't",
    "we",
    "we'd",
    "we'll",
    "we're",
    "we've",
    "were",
    "weren't",
    "what",
    "what's",
    "when",
    "when's",
    "where",
    "where's",
    "which",
    "while",
    "who",
    "who's",
    "whom",
    "why",
    "why's",
    "with",
    "won't",
    "would",
    "wouldn't",
    "you",
    "you'd",
    "you'll",
    "you're",
    "you've",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "tell",
    "show",
    "give",
    "please",
}


@dataclass
class SearchResult:
    chunk_id: int
    document_id: int
    document_title: str
    content: str
    dense_rank: int = 0
    sparse_rank: int = 0
    score: float = 0.0
    similarity: float = 0.0


def is_header_or_contact_query(query: str) -> bool:
    """Detect whether query asks about personal contact, location, author, or overview."""
    q_low = query.lower()
    contact_terms = {
        "email",
        "mail",
        "phone",
        "mobile",
        "cell",
        "telephone",
        "contact",
        "call",
        "reach",
        "number",
        "linkedin",
        "github",
    }
    location_terms = {
        "live",
        "reside",
        "residence",
        "address",
        "location",
        "city",
        "country",
        "hometown",
        "based",
        "from",
    }
    identity_terms = {
        "who am i",
        "who is",
        "author",
        "candidate",
        "whose cv",
        "whose resume",
        "my name",
        "full name",
        "profile",
        "contact info",
        "contact details",
        "about me",
        "bio",
        "summary",
        "overview",
        "introduction",
        "header",
    }
    words = set(re.findall(r"\b[a-z0-9_-]+\b", q_low))
    if any(t in words for t in contact_terms):
        return True
    if any(t in words for t in location_terms) and any(
        w in words
        for w in ("where", "address", "live", "city", "location", "from", "country", "reside")
    ):
        return True
    return any(phrase in q_low for phrase in identity_terms)


def build_fts_query(query: str) -> str:
    """Preprocess query into an effective FTS5 BM25 query."""
    raw_tokens = [w for w in re.findall(r"[a-zA-Z0-9_\-\@\.]+", query.lower()) if len(w) > 1]
    if not raw_tokens:
        clean = "".join(c for c in query if c.isalnum() or c.isspace()).strip()
        return clean or query.strip()

    meaningful = [t for t in raw_tokens if t not in STOP_WORDS]
    if not meaningful:
        meaningful = raw_tokens

    expanded = list(meaningful)
    has_email = any(t in {"email", "mail"} for t in meaningful)
    if has_email:
        expanded.extend(["gmail*", "yahoo*", "hotmail*", "outlook*", "@*"])
    has_contact = any(
        t in {"contact", "phone", "mobile", "cell", "call", "reach"} for t in meaningful
    )
    if has_contact:
        expanded.extend(["phone*", "mobile*", "contact*"])
    has_location = any(
        t in {"live", "reside", "address", "location", "city", "country", "where"}
        for t in meaningful
    )
    if has_location:
        expanded.extend(["address*", "location*", "city*"])

    safe_terms: list[str] = []
    for t in expanded:
        clean_t = re.sub(r"[^\w*]", "", t)
        if clean_t and clean_t != "*":
            safe_terms.append(clean_t)

    if not safe_terms:
        safe_terms = [re.sub(r"[^\w]", "", w) for w in raw_tokens if re.sub(r"[^\w]", "", w)]

    unique = list(dict.fromkeys(safe_terms))
    return " OR ".join(unique)


async def hybrid_search(
    session: AsyncSession,
    query: str,
    top_k: int | None = None,
    dense_weight: float | None = None,
    sparse_weight: float | None = None,
    session_id: str | None = None,
    min_similarity: float | None = None,
    relative_threshold: float | None = None,
) -> list[SearchResult]:
    """Perform hybrid retrieval and return top_k ranked results.

    Applies both an absolute minimum similarity threshold and an adaptive
    relative drop-off cutoff so only truly related citations are returned (1 to top_k).
    """
    top_k = top_k or settings.top_k_retrieval
    dw = dense_weight if dense_weight is not None else settings.dense_weight
    sw = sparse_weight if sparse_weight is not None else settings.sparse_weight
    min_sim = min_similarity if min_similarity is not None else settings.similarity_threshold
    rel_thresh = (
        relative_threshold if relative_threshold is not None else settings.relative_score_threshold
    )

    # Normalize weights
    total = dw + sw
    if total > 0:
        dw, sw = dw / total, sw / total
    else:
        dw, sw = 0.5, 0.5

    query_vec = await embed_query(query)

    # Fetch broader candidate pool for high-recall fusion
    dense_results = await _dense_search(
        session, query_vec, top_k * 2, session_id=session_id, min_similarity=min_sim
    )
    sparse_results = await _sparse_search(session, query, top_k * 2, session_id=session_id)

    # Contextual Header & Contact Anchoring
    if is_header_or_contact_query(query):
        sparse_results = await _anchor_header_chunks(
            session,
            query,
            query_vec,
            dense_results,
            sparse_results,
            session_id=session_id,
        )

    merged = _rrf_merge(
        dense_results,
        sparse_results,
        dw,
        sw,
        top_k,
        min_similarity=min_sim,
        relative_threshold=rel_thresh,
    )
    return merged


async def _anchor_header_chunks(
    session: AsyncSession,
    query: str,
    query_vec: list[float],
    dense_results: list[dict],
    sparse_results: list[dict],
    session_id: str | None = None,
) -> list[dict]:
    """Evaluate and anchor document header/metadata chunks (chunk_index == 0).

    In CVs, resumes, reports, and papers, Chunk 0 contains header metadata:
    author name, contact email, phone, location/residence, and summary.
    When a query asks about these attributes, Chunk 0 is evaluated and elevated.
    """
    cutoff = get_session_cutoff()
    params: dict = {"cutoff": cutoff}
    where_sql = "c.chunk_index IN (0, 1) AND d.created_at >= :cutoff"
    if session_id:
        where_sql += " AND d.session_id = :session_id"
        params["session_id"] = session_id

    query_sql = f"""
        SELECT c.id, c.document_id, c.content, c.embedding_json, d.title
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE {where_sql}
    """
    rows = await session.execute(text(query_sql), params)
    q_low = query.lower()

    for row in rows:
        content = row.content
        has_match = False

        # 1. Email inquiries (e.g. "email", "email address", "mail")
        if "email" in q_low or "mail" in q_low:
            if re.search(r"[\w\.-]+@[\w\.-]+\.\w+", content):
                has_match = True
        # 2. Phone / contact inquiries (e.g. "phone", "mobile", "contact number")
        elif any(
            w in q_low
            for w in ("phone", "mobile", "cell", "telephone", "contact", "call", "number")
        ):
            if re.search(r"\b09\d{9}\b|\+?\d{10,13}\b|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", content):
                has_match = True
        # 3. Location / residence inquiries (e.g. "where do I live", "my address", "residence")
        elif any(
            w in q_low
            for w in (
                "live",
                "where",
                "address",
                "reside",
                "residence",
                "city",
                "country",
                "location",
                "based",
                "from",
            )
        ):
            if re.search(
                r"\b(taguig|manila|philippines|ncr|cebu|davao|street|st\.|ave|avenue|road|rd\.|blvd|city|province|country|state|zip|postal|residence|residing|address:?)\b",
                content,
                re.IGNORECASE,
            ):
                has_match = True
        # 4. Identity / author / document subject inquiries (e.g. "who am I", "whose CV", "my name")
        elif any(
            w in q_low
            for w in (
                "who",
                "author",
                "whose",
                "name",
                "candidate",
                "profile",
                "summary",
                "overview",
            )
        ):
            has_match = True

        if has_match:
            # Remove any lower-ranked duplicate of this chunk from sparse_results
            sparse_results = [s for s in sparse_results if s["chunk_id"] != row.id]
            # Anchor at top rank (rank 1) with high score
            sparse_results.insert(
                0,
                {
                    "chunk_id": row.id,
                    "document_id": row.document_id,
                    "document_title": row.title,
                    "content": row.content,
                    "score": 10.0,
                },
            )
            # Ensure Chunk 0 is evaluated in dense results
            if not any(d["chunk_id"] == row.id for d in dense_results) and row.embedding_json:
                try:
                    c_vec = json.loads(row.embedding_json)
                    sim = _cosine_similarity(query_vec, c_vec)
                    dense_results.append(
                        {
                            "chunk_id": row.id,
                            "document_id": row.document_id,
                            "document_title": row.title,
                            "content": row.content,
                            "score": sim,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("Could not compute Chunk 0 similarity: %s", exc)

    return sparse_results


async def _dense_search(
    session: AsyncSession,
    query_vec: list[float],
    top_k: int,
    session_id: str | None = None,
    min_similarity: float = 0.45,
) -> list[dict]:
    """Fetch all chunk embeddings, filter by min_similarity, and rank by cosine similarity."""
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
        # Filter out chunks below relevance threshold
        if sim >= min_similarity:
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
    bind = session.bind
    dialect_name = getattr(bind.dialect, "name", "sqlite") if bind else "sqlite"
    is_sqlite = dialect_name == "sqlite" and settings.database_url.startswith("sqlite")
    fts_q = build_fts_query(query)

    if is_sqlite and fts_q:
        try:
            params: dict = {"q": fts_q, "k": top_k, "cutoff": cutoff}
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

    # Fallback / PostgreSQL search using word boundaries with meaningful tokens
    raw_tokens = [
        w
        for w in re.findall(r"[a-zA-Z0-9_\-\@\.]+", query.lower())
        if len(w) > 2 and w not in STOP_WORDS
    ]
    if not raw_tokens:
        raw_tokens = [query.strip()]

    if dialect_name == "postgresql":
        # In PostgreSQL, match whole words via regex word boundaries (\m and \M)
        # Prevents substrings like 'deliveries' from matching 'live'
        safe_words = [re.escape(w) for w in raw_tokens if w]
        regex_pattern = r"\m(" + "|".join(safe_words) + r")\M"
        where_sql = "c.content ~* :pattern AND d.created_at >= :cutoff"
        params = {"pattern": regex_pattern, "k": top_k, "cutoff": cutoff}
        if session_id:
            where_sql += " AND d.session_id = :session_id"
            params["session_id"] = session_id
        try:
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
        except Exception as exc:  # noqa: BLE001
            log.warning("Postgres regex search failed: %s", exc)
            await session.rollback()

    # SQLite fallback LIKE
    like_clauses = [f"c.content LIKE :q_{idx}" for idx in range(len(raw_tokens))]
    like_sql = " OR ".join(like_clauses) if like_clauses else "c.content LIKE :q_0"

    params = {"cutoff": cutoff, "k": top_k}
    for idx, token in enumerate(raw_tokens):
        params[f"q_{idx}"] = f"%{token}%"
    if session_id:
        params["session_id"] = session_id

    where_sql = f"({like_sql}) AND d.created_at >= :cutoff"
    if session_id:
        where_sql += " AND d.session_id = :session_id"

    try:
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
    except Exception as exc:  # noqa: BLE001
        log.warning("LIKE fallback search failed: %s", exc)
        await session.rollback()
        return []


def _rrf_merge(
    dense: list[dict],
    sparse: list[dict],
    dense_weight: float,
    sparse_weight: float,
    top_k: int,
    min_similarity: float = 0.50,
    relative_threshold: float = 0.80,
) -> list[SearchResult]:
    """Merge ranked lists using Reciprocal Rank Fusion with adaptive relevance pruning.

    Enforces that non-related chunks are pruned rather than included simply to
    fill the top_k quota. Top_k serves as the maximum limit, returning only 1-top_k
    citations based on relative score drop-off.
    """
    registry: dict[int, SearchResult] = {}

    for rank, d in enumerate(dense, start=1):
        cid = d["chunk_id"]
        sim = float(d.get("score", 0.0))
        if cid not in registry:
            registry[cid] = SearchResult(
                chunk_id=cid,
                document_id=d["document_id"],
                document_title=d["document_title"],
                content=d["content"],
                similarity=sim,
            )
        else:
            registry[cid].similarity = max(registry[cid].similarity, sim)
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

    if not registry:
        return []

    ranked = sorted(registry.values(), key=lambda r: r.score, reverse=True)
    candidates = ranked[:top_k]

    # Calculate highest semantic similarity and highest fusion score among candidates
    top_sim = max((c.similarity for c in candidates), default=0.0)
    sim_cutoff = max(min_similarity, top_sim * relative_threshold)
    top_score = candidates[0].score if candidates else 0.0
    score_cutoff = top_score * relative_threshold

    filtered: list[SearchResult] = []
    for c in candidates:
        is_score_qualified = c.score >= score_cutoff
        is_strong_dense = c.similarity >= sim_cutoff
        is_hybrid_corroborated = c.sparse_rank > 0 and c.dense_rank > 0
        is_top_sparse = c.sparse_rank == 1 and (
            c.similarity >= (min_similarity * 0.80) or c.similarity == 0.0
        )

        # A candidate is included only if it is within relative score distance of top score
        # and has semantic or hybrid verification
        if is_score_qualified and (is_strong_dense or is_hybrid_corroborated or is_top_sparse):
            filtered.append(c)

    # If all candidates missed cutoff but candidates exist with similarity >= min_similarity
    # or top sparse match, preserve only the single best match
    if (
        not filtered
        and candidates
        and (candidates[0].similarity >= min_similarity or candidates[0].sparse_rank > 0)
    ):
        filtered.append(candidates[0])

    return filtered


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
