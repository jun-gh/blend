"""Document text extraction utilities."""

from __future__ import annotations

import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

log = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract readable text from PDF bytes using pypdf."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text: list[str] = []
        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            stripped = page_text.strip()
            if stripped:
                pages_text.append(f"--- Page {idx + 1} ---\n{stripped}")
        return "\n\n".join(pages_text)
    except PdfReadError as exc:
        log.warning("PDF reading error: %s", exc)
        raise ValueError(f"Failed to parse PDF document: {exc}") from exc
    except Exception as exc:
        log.warning("Unexpected error extracting PDF text: %s", exc)
        raise ValueError(f"Could not extract text from PDF: {exc}") from exc


def extract_text_from_upload(filename: str, content_bytes: bytes) -> str:
    """Extract text from uploaded bytes based on file format."""
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        return extract_text_from_pdf(content_bytes)

    # Text formats (.txt, .md, .csv, .json, etc.)
    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return content_bytes.decode("latin-1", errors="replace")
