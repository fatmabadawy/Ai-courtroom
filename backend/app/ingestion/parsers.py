"""
backend/app/ingestion/parsers.py
──────────────────────────────────
Text extraction for the file types the demo needs: PDF, DOCX, TXT.

Each parser returns a list of (page_number_or_None, text) tuples so the
chunker downstream can preserve a rough page/section reference for
citations. Plain-text files have no natural page concept, so they yield a
single (None, full_text) entry.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

PageText = Tuple[Optional[int], str]


class UnsupportedFileTypeError(ValueError):
    pass


def extract_text(file_path: str, content_type: str) -> List[PageText]:
    """
    Dispatch to the right parser based on content_type (falling back to the
    file extension if content_type is generic/missing).
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if content_type == "application/pdf" or suffix == ".pdf":
        return _extract_pdf(path)
    if (
        content_type
        in (
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        or suffix in (".doc", ".docx")
    ):
        return _extract_docx(path)
    if content_type == "text/plain" or suffix == ".txt":
        return _extract_txt(path)

    raise UnsupportedFileTypeError(
        f"No text extractor for content_type={content_type!r}, suffix={suffix!r}"
    )


def _extract_pdf(path: Path) -> List[PageText]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: List[PageText] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((i, text))
    return pages


def _extract_docx(path: Path) -> List[PageText]:
    import docx

    doc = docx.Document(str(path))
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    # DOCX has no reliable page boundaries without a rendering engine, so
    # this is returned as one logical "page".
    return [(None, full_text)] if full_text.strip() else []


def _extract_txt(path: Path) -> List[PageText]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [(None, text)] if text.strip() else []
