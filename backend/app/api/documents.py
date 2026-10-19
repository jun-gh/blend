"""Documents CRUD and ingestion endpoints."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import require_site_auth
from app.core.session import get_session_cutoff, get_session_id, prune_expired_documents
from app.models.orm import Chunk, Document
from app.models.schemas import (
    DocumentCreate,
    DocumentList,
    DocumentRead,
    ExtractedTextResponse,
)
from app.services.extractor import extract_text_from_upload
from app.services.ingestion import ingest_document

router = APIRouter(dependencies=[Depends(require_site_auth)])


@router.post("/", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: DocumentCreate,
    session: AsyncSession = Depends(get_session),
    session_id: str = Depends(get_session_id),
) -> DocumentRead:
    """Ingest a new document into the knowledge base under the caller's session."""
    await prune_expired_documents(session)

    cutoff = get_session_cutoff()
    count_stmt = select(func.count(Document.id)).where(
        Document.session_id == session_id, Document.created_at >= cutoff
    )
    res = await session.execute(count_stmt)
    current_count = res.scalar_one()

    if current_count >= settings.max_documents_per_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Session document limit reached ({current_count}/"
                f"{settings.max_documents_per_session}). "
                "Please delete an existing document before adding more."
            ),
        )

    doc = await ingest_document(session, payload, session_id=session_id)
    return DocumentRead.model_validate(doc)


@router.post("/extract-text", response_model=ExtractedTextResponse)
async def extract_text_endpoint(
    file: UploadFile = File(...),
) -> ExtractedTextResponse:
    """Extract text from an uploaded document (PDF, TXT, MD, CSV, JSON)."""
    filename = file.filename or "uploaded_file"
    try:
        content = await file.read()
        extracted = extract_text_from_upload(filename, content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract text from file: {exc}",
        ) from exc

    if not extracted.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text could be extracted from this document.",
        )

    return ExtractedTextResponse(text=extracted, filename=filename)


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    source: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    session_id: str = Depends(get_session_id),
) -> DocumentRead:
    """Upload and ingest a file directly into the knowledge base under the caller's session."""
    await prune_expired_documents(session)

    cutoff = get_session_cutoff()
    count_stmt = select(func.count(Document.id)).where(
        Document.session_id == session_id, Document.created_at >= cutoff
    )
    res = await session.execute(count_stmt)
    current_count = res.scalar_one()

    if current_count >= settings.max_documents_per_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Session document limit reached ({current_count}/"
                f"{settings.max_documents_per_session}). "
                "Please delete an existing document before adding more."
            ),
        )

    filename = file.filename or "uploaded_file"
    try:
        content = await file.read()
        extracted = extract_text_from_upload(filename, content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse uploaded file: {exc}",
        ) from exc

    if not extracted.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file contains no readable text.",
        )

    doc_title = title.strip() if title and title.strip() else filename.rsplit(".", 1)[0]
    payload = DocumentCreate(title=doc_title, content=extracted, source=source)
    doc = await ingest_document(session, payload, session_id=session_id)
    return DocumentRead.model_validate(doc)


@router.get("/", response_model=DocumentList)
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    session_id: str = Depends(get_session_id),
) -> DocumentList:
    """Return a paginated list of ingested documents for the active session."""
    await prune_expired_documents(session)

    cutoff = get_session_cutoff()
    base_where = (Document.session_id == session_id, Document.created_at >= cutoff)

    result = await session.execute(
        select(Document)
        .where(*base_where)
        .offset(skip)
        .limit(limit)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()

    count_result = await session.execute(select(func.count(Document.id)).where(*base_where))
    total = count_result.scalar_one()

    return DocumentList(
        total=total,
        max_documents=settings.max_documents_per_session,
        items=[DocumentRead.model_validate(d) for d in docs],
    )


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    session_id: str = Depends(get_session_id),
) -> DocumentRead:
    """Fetch a single document by ID within the active session."""
    doc = await session.get(Document, document_id)
    if not doc or doc.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DocumentRead.model_validate(doc)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    session_id: str = Depends(get_session_id),
) -> Response:
    """Delete a document and its chunks from the active session."""
    doc = await session.get(Document, document_id)
    if not doc or doc.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # Delete related chunks
    chunks_res = await session.execute(select(Chunk).where(Chunk.document_id == document_id))
    chunks = chunks_res.scalars().all()

    # Clean up SQLite FTS5 table if active
    if settings.database_url.startswith("sqlite"):
        try:
            for c in chunks:
                await session.execute(
                    text("DELETE FROM chunks_fts WHERE rowid = :rid"),
                    {"rid": c.id},
                )
        except Exception:
            pass

    for c in chunks:
        await session.delete(c)

    await session.delete(doc)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
