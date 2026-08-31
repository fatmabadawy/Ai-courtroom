"""
backend/app/ingestion/chunker.py
───────────────────────────────────
Simple, dependency-free text chunker. Splits on paragraph boundaries first,
then greedily packs paragraphs into chunks up to `max_chars`, so chunks
don't cut sentences mid-word and stay a reasonable size for embedding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Chunk:
    index: int
    text: str
    page_number: Optional[int]


def chunk_pages(
    pages: List[tuple],
    max_chars: int = 800,
    overlap_chars: int = 100,
) -> List[Chunk]:
    """
    pages: list of (page_number_or_None, text) — as returned by
    ingestion.parsers.extract_text().

    Returns chunks in document order, each tagged with the page it came
    from (best-effort — a chunk that happens to span a page boundary keeps
    the page it started on).
    """
    chunks: List[Chunk] = []
    index = 0

    for page_number, text in pages:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        current = ""

        for para in paragraphs:
            candidate = f"{current}\n{para}".strip() if current else para
            if len(candidate) > max_chars and current:
                chunks.append(Chunk(index=index, text=current, page_number=page_number))
                index += 1
                # Keep a small overlap for context continuity across chunks.
                tail = current[-overlap_chars:] if overlap_chars else ""
                current = f"{tail}\n{para}".strip()
            else:
                current = candidate

        if current:
            chunks.append(Chunk(index=index, text=current, page_number=page_number))
            index += 1

    return chunks
