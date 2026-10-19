"""SQLAlchemy ORM models.

Local (SQLite):  stores embeddings as JSON-serialised float arrays.
Production (Postgres + pgvector): stores embeddings as VECTOR columns.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Document(Base):
    """A source document ingested into the knowledge base."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    session_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False, default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class Chunk(Base):
    """A text chunk derived from a Document, with its embedding."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Embeddings stored as JSON in SQLite; migrate to pgvector VECTOR column in Postgres
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------
    def get_embedding(self) -> list[float] | None:
        """Deserialise the stored JSON embedding."""
        if self.embedding_json is None:
            return None
        return json.loads(self.embedding_json)

    def set_embedding(self, vector: list[float]) -> None:
        """Serialise and store the embedding vector."""
        self.embedding_json = json.dumps(vector)
