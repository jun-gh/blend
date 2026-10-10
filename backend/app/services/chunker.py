"""Text chunking utilities.

Splits long documents into overlapping chunks suitable for embedding.
"""

from __future__ import annotations

from typing import List


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> List[str]:
    """Split *text* into overlapping character-level windows.

    Args:
        text:          The raw document text.
        chunk_size:    Maximum number of characters per chunk.
        chunk_overlap: Characters shared between adjacent chunks.

    Returns:
        Ordered list of chunk strings.
    """
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - chunk_overlap

    return chunks
