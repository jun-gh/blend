"""Document text extraction utilities."""

from __future__ import annotations

import io
import logging
import re

log = logging.getLogger(__name__)


def clean_extracted_text(text: str) -> str:
    """Normalize extracted document text.

    Removes pathological single-word line breaks commonly produced by PDF word-by-word
    extraction, cleans unicode whitespace, collapses multi-spaces, and normalizes
    paragraph spacing so text chunks maintain sentence continuity.
    """
    if not text:
        return ""

    # 1. Standardize unicode spaces and line endings
    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")

    # 2. Blank lines with whitespace -> clean newline
    text = re.sub(r"^[ \t]+$", "", text, flags=re.MULTILINE)

    # 3. Collapse pathological PDF word-per-line breaks:
    # E.g., 'word\n \nword' or 'word\n\nword' when neither is a bullet or heading
    text = re.sub(r"(\S)[ \t]*\n[ \t]*\n[ \t]*(\S)", r"\1 \2", text)

    # 4. Clean single linebreaks inside mid-sentence lines
    text = re.sub(r"(?<=[a-zA-Z0-9,;/|])\n(?=[a-zA-Z0-9(|/])", r" ", text)

    # 5. Collapse multiple horizontal spaces/tabs
    text = re.sub(r"[ \t]+", " ", text)

    # 6. Normalize paragraph breaks (max 2 consecutive newlines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract readable text from PDF bytes using pypdf."""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as err:
        log.warning("pypdf is not installed: %s", err)
        raise ValueError(
            "PDF extraction requires 'pypdf'. Please run 'pip install pypdf'."
        ) from err

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text: list[str] = []
        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            cleaned = clean_extracted_text(page_text)
            if cleaned:
                pages_text.append(f"--- Page {idx + 1} ---\n{cleaned}")
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
        raw_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw_text = content_bytes.decode("latin-1", errors="replace")

    return clean_extracted_text(raw_text)
