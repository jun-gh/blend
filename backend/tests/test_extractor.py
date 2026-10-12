"""Unit tests for document text extractor."""

from __future__ import annotations

import io

import pytest

from app.services.extractor import extract_text_from_pdf, extract_text_from_upload

pypdf = pytest.importorskip("pypdf")
PdfWriter = pypdf.PdfWriter


def test_extract_text_from_txt_upload():
    raw = b"Hello, this is a plain text file."
    result = extract_text_from_upload("notes.txt", raw)
    assert result == "Hello, this is a plain text file."


def test_extract_text_from_markdown_upload():
    raw = b"# Heading\n\nSome **markdown** content."
    result = extract_text_from_upload("README.md", raw)
    assert "# Heading" in result
    assert "Some **markdown** content." in result


def test_extract_text_from_pdf():
    # Generate a simple in-memory valid PDF
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    # Note: blank page will have empty text, verify it doesn't crash
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    result = extract_text_from_pdf(pdf_bytes)
    assert isinstance(result, str)


def test_extract_invalid_pdf_raises():
    with pytest.raises(ValueError, match="Failed to parse PDF document"):
        extract_text_from_pdf(b"not a valid pdf content")
