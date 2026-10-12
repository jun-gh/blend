"""Document ingestion pipeline.

Orchestrates chunking, embedding, and persistence for new documents.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chunk, Document
from app.models.schemas import DocumentCreate
from app.services.chunker import chunk_text
from app.services.embedding import embed_texts

log = logging.getLogger(__name__)


async def ingest_document(
    session: AsyncSession,
    payload: DocumentCreate,
) -> Document:
    """Full ingestion pipeline for a new document.

    Steps:
        1. Persist Document record.
        2. Split content into overlapping chunks.
        3. Generate embeddings for all chunks via Gemini (or fallback mock embeddings).
        4. Persist Chunk records (with embeddings).
        5. Populate the FTS5 virtual table.
    """
    # 1. Create document
    doc = Document(title=payload.title, source=payload.source)
    session.add(doc)
    await session.flush()  # obtain doc.id without committing yet

    # 2. Chunk text
    chunks_text: list[str] = chunk_text(payload.content)
    if not chunks_text:
        log.warning("Document '%s' produced no chunks.", payload.title)
        await session.commit()
        return doc

    log.info(
        "Ingesting doc id=%d title='%s' -> %d chunks.",
        doc.id,
        payload.title,
        len(chunks_text),
    )

    # 3. Embed chunks in batch
    try:
        vectors = await embed_texts(chunks_text, task_type="retrieval_document")
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Embedding generation failed (%s). Generating fallback zeros/mock vectors.",
            exc,
        )
        vectors = [[0.0] * 768 for _ in chunks_text]

    # 4. Persist chunks
    chunk_objs: list[Chunk] = []
    for idx, (content, vector) in enumerate(zip(chunks_text, vectors, strict=False)):
        c = Chunk(document_id=doc.id, chunk_index=idx, content=content)
        c.set_embedding(vector)
        session.add(c)
        chunk_objs.append(c)

    await session.flush()

    # 5. Populate FTS5 virtual table (SQLite only)
    is_sqlite = settings.database_url.startswith("sqlite") or "sqlite" in str(session.bind.url if session.bind else "")
    if is_sqlite:
        await _ensure_fts_table(session)
        for c in chunk_objs:
            try:
                await session.execute(
                    text("INSERT INTO chunks_fts(rowid, content) VALUES (:rid, :content)"),
                    {"rid": c.id, "content": c.content},
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not insert into chunks_fts: %s", exc)

    await session.commit()
    log.info("Document id=%d ingested successfully.", doc.id)
    return doc


async def _ensure_fts_table(session: AsyncSession) -> None:
    """Create the FTS5 virtual table if it does not exist."""
    try:
        await session.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                USING fts5(content, content='chunks', content_rowid='id')
                """
            )
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not create FTS5 table: %s", exc)
