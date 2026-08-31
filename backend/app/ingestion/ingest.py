"""
backend/app/ingestion/ingest.py
──────────────────────────────────
Orchestrates: extract text → chunk → embed → persist chunks + evidence rows.

This is the function backend/app/api/routers/documents.py already looks
for (`from backend.app.ingestion.ingest import ingest_document`) — it was
previously always falling back to `_stub_ingest`, which recorded nothing
beyond the raw document row. Now real parsing/chunking/embedding happens
here, feeding backend/app/rag/retrieve_real.py's search over document
content.
"""

from __future__ import annotations

import hashlib
import logging

from backend.app.database import client as db
from backend.app.ingestion.chunker import chunk_pages
from backend.app.ingestion.parsers import UnsupportedFileTypeError, extract_text
from backend.app.rag.embeddings import get_backend

logger = logging.getLogger(__name__)

# Document type is inferred from filename/content heuristically for now —
# a real system might classify with a model; this is a light-weight,
# explainable heuristic that's good enough for the demo's evidence types.
_TYPE_KEYWORDS = {
    "contract": ("agreement", "contract", "clause", "party", "hereby"),
    "email": ("from:", "to:", "subject:", "sent:"),
    "witness_statement": ("i confirm", "i declare", "witness", "testify"),
}


def _infer_document_type(text: str) -> str:
    lower = text.lower()
    for doc_type, keywords in _TYPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return doc_type
    return "other"


async def ingest_document(document_id: str, case_id: str, file_path: str) -> None:
    """
    Real ingestion pipeline. Failure here should not crash the upload
    endpoint — the document row already exists with status 'uploaded';
    on any error this marks it 'failed' rather than raising, so the
    caller (documents.py) can still return a 201 with a document the
    user can see and retry.
    """
    doc = await db.get_document(document_id)
    content_type = doc["content_type"] if doc else "application/octet-stream"

    try:
        pages = extract_text(file_path, content_type)
        full_text = "\n\n".join(text for _, text in pages)

        if not full_text.strip():
            await db.update_document_ingestion(
                document_id,
                content_hash="",
                extracted_text="",
                document_type="other",
                status="processed",
            )
            logger.warning(
                "Document %s produced no extractable text (empty/unsupported content).",
                document_id,
            )
            return

        content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        document_type = _infer_document_type(full_text)

        chunks = chunk_pages(pages)
        backend = get_backend()

        chunk_texts = [c.text for c in chunks]
        if backend.is_stable:
            # Sentence-transformer path: embed once, store the vector —
            # it's directly comparable to a query embedded later.
            embeddings = backend.embed(chunk_texts)
        else:
            # TF-IDF fallback: not stable across separate fit() calls (see
            # embeddings.py docstring), so storing a vector fit only on
            # this document's own chunks would NOT be comparable to a
            # query embedded later against a different corpus. Store a
            # placeholder; retrieve_real.py refits TF-IDF over the full
            # case corpus + query together at retrieval time instead.
            embeddings = [[] for _ in chunk_texts]

        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = await db.insert_chunk(
                document_id=document_id,
                case_id=case_id,
                chunk_index=chunk.index,
                content=chunk.text,
                embedding=embedding,
                page_number=chunk.page_number,
            )
            await db.create_evidence(
                case_id=case_id,
                document_id=document_id,
                chunk_id=chunk_id,
                content=chunk.text,
                source_type="USER_PROVIDED",
                relevance_score=0.0,  # relevance is query-dependent; set at retrieval time
            )

        await db.update_document_ingestion(
            document_id,
            content_hash=content_hash,
            extracted_text=full_text,
            document_type=document_type,
            status="processed",
        )
        logger.info(
            "Ingested document %s: %d chunks, type=%s, embedding_backend=%s",
            document_id,
            len(chunks),
            document_type,
            backend.name,
        )

    except UnsupportedFileTypeError as exc:
        logger.warning("Unsupported file type for document %s: %s", document_id, exc)
        await db.update_document_ingestion(
            document_id, content_hash="", extracted_text="", document_type="other", status="failed"
        )
    except Exception as exc:
        logger.exception("Ingestion failed for document %s: %s", document_id, exc)
        await db.update_document_ingestion(
            document_id, content_hash="", extracted_text="", document_type="other", status="failed"
        )
