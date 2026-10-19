"""Pydantic v2 request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------
class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    content: str = Field(..., min_length=1)
    source: str | None = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source: str | None
    session_id: str = ""
    created_at: datetime
    updated_at: datetime


class DocumentList(BaseModel):
    total: int
    max_documents: int = 10
    items: list[DocumentRead]


class ExtractedTextResponse(BaseModel):
    text: str
    filename: str


# ---------------------------------------------------------------------------
# Query / RAG schemas
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    dense_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    sparse_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    session_id: str | None = None


class SourceChunk(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    content: str
    score: float


class QueryResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    answer: str
    sources: list[SourceChunk]
    query: str
    model: str
    model_name: str
    retrieval_ms: float
    generation_ms: float


# ---------------------------------------------------------------------------
# Auth & System Config schemas
# ---------------------------------------------------------------------------
class AuthStatusResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    required: bool
    model: str
    model_name: str


class ModelConfigResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model: str
    model_name: str
    embed_model: str


class PasswordVerifyRequest(BaseModel):
    password: str = Field(..., min_length=1)


class AuthTokenResponse(BaseModel):
    token: str
    expires_at: int
