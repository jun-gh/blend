"""Pydantic v2 request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------
class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    content: str = Field(..., min_length=1)
    source: Optional[str] = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source: Optional[str]
    created_at: datetime
    updated_at: datetime


class DocumentList(BaseModel):
    total: int
    items: List[DocumentRead]


# ---------------------------------------------------------------------------
# Query / RAG schemas
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    dense_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    sparse_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class SourceChunk(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    content: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    query: str
    model: str
    retrieval_ms: float
    generation_ms: float
