"""Session identification and document lifecycle management.

Provides session extraction from headers and automatic pruning of expired
documents based on settings.session_expiry_days.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Header
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.orm import Chunk, Document

log = logging.getLogger(__name__)


def get_session_id(
    x_session_id: str | None = Header(None, alias="X-Session-ID")
) -> str:
    """Extract or generate a client session ID from the X-Session-ID header."""
    if x_session_id:
        cleaned = x_session_id.strip()
        if cleaned:
            return cleaned
    return f"sess_{uuid.uuid4().hex[:16]}"


def get_session_cutoff() -> datetime:
    """Return the UTC timestamp threshold before which documents are expired."""
    days = max(1, settings.session_expiry_days)
    return datetime.now(UTC) - timedelta(days=days)


async def prune_expired_documents(session: AsyncSession) -> int:
    """Delete documents older than the session expiry threshold and their chunks.

    Returns:
        Number of expired documents removed.
    """
    cutoff = get_session_cutoff()
    expired_stmt = select(Document.id).where(Document.created_at < cutoff)
    result = await session.execute(expired_stmt)
    expired_ids = list(result.scalars().all())

    if not expired_ids:
        return 0

    log.info("Pruning %d expired document(s) created before %s", len(expired_ids), cutoff)

    # 1. Clean up FTS5 virtual table if using SQLite
    if settings.database_url.startswith("sqlite"):
        try:
            chunks_stmt = select(Chunk.id).where(Chunk.document_id.in_(expired_ids))
            chunk_rows = await session.execute(chunks_stmt)
            chunk_ids = list(chunk_rows.scalars().all())
            for cid in chunk_ids:
                await session.execute(
                    text("DELETE FROM chunks_fts WHERE rowid = :rid"),
                    {"rid": cid},
                )
        except Exception as exc:
            log.warning("FTS cleanup during document pruning encountered error: %s", exc)

    # 2. Delete chunks
    await session.execute(delete(Chunk).where(Chunk.document_id.in_(expired_ids)))

    # 3. Delete documents
    await session.execute(delete(Document).where(Document.id.in_(expired_ids)))
    await session.commit()

    return len(expired_ids)
