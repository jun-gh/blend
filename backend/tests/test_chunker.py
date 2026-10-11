"""Unit tests for the chunker and text splitting utilities."""

from app.services.chunker import chunk_text


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_chunk_text_short():
    text = "Short text under chunk size."
    chunks = chunk_text(text, chunk_size=512, chunk_overlap=64)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_overlapping():
    text = "A" * 1000
    chunks = chunk_text(text, chunk_size=500, chunk_overlap=100)
    assert len(chunks) > 1
    # Check that chunks share overlap
    assert len(chunks[0]) == 500
