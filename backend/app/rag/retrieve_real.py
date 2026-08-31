"""
backend/app/rag/retrieve_real.py
────────────────────────────────────
Plan B's real retrieve() — INTERFACES.md §6 signature, self-contained
local implementation (no paid/hosted API):

  1. Embed the query with the same backend used at ingestion time
     (backend/app/rag/embeddings.py — sentence-transformers, or a TF-IDF
     fallback if the model can't be loaded offline).
  2. Compare against document_chunks for this case_id, ranked by cosine
     similarity.
  3. Return the top_k chunks as EvidenceResult, matching each chunk to its
     already-persisted `evidence` row (created at ingestion time by
     ingestion/ingest.py) so evidence_id stays consistent across the
     system.

`retrieve()` itself must stay SYNCHRONOUS (agents call it directly, no
event loop) even though the real chunk data lives in the async aiosqlite
database used by the FastAPI layer — so this reads via a plain sync
sqlite3 connection, the same pattern used by graph/run.py's
_load_case_description for the same reason.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import List, Optional

from backend.app.database.client import database_path
from backend.app.models.schemas import EvidenceResult
from backend.app.rag.embeddings import cosine_similarity, get_backend

logger = logging.getLogger(__name__)


def _fetch_chunks_and_evidence(case_id: str) -> List[dict]:
    """
    Join document_chunks with their evidence row (created 1:1 at ingestion
    time) so each result already has a real, persisted evidence_id.
    """
    db_path = database_path()
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                c.chunk_id, c.content, c.embedding, c.page_number, c.document_id,
                e.evidence_id, e.source_type, e.relevance_score
            FROM document_chunks c
            LEFT JOIN evidence e ON e.chunk_id = c.chunk_id
            WHERE c.case_id = ?
            ORDER BY c.document_id, c.chunk_index
            """,
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def retrieve(
    case_id: str,
    query: str,
    top_k: int = 8,
    filters: Optional[dict] = None,
) -> List[EvidenceResult]:
    """
    Real retrieve() implementation. Signature matches INTERFACES.md §6
    exactly.

    Returns an empty list (not an error) if no documents have been
    ingested for this case yet — callers (fact_checker, prosecution,
    defense) already handle empty evidence_ids as a valid "no evidence
    found" outcome per PLAN_C/PLAN_D's anti-hallucination requirements.
    """
    rows = _fetch_chunks_and_evidence(case_id)
    if filters and "evidence_id" in filters:
        rows = [r for r in rows if r.get("evidence_id") == filters["evidence_id"]]

    if not rows:
        return []

    backend = get_backend()

    if backend.is_stable:
        query_vec = backend.embed([query])[0]
        scored = []
        for row in rows:
            stored = row.get("embedding")
            try:
                chunk_vec = json.loads(stored) if isinstance(stored, str) else stored
            except (TypeError, json.JSONDecodeError):
                chunk_vec = None
            if not chunk_vec:
                continue
            score = cosine_similarity(query_vec, chunk_vec)
            scored.append((score, row))
    else:
        # TF-IDF fallback: not stable across separate fit() calls, so fit
        # fresh over (all this case's chunk texts + the query) together —
        # see embeddings.py docstring for why.
        texts = [r["content"] for r in rows] + [query]
        vectors = backend.embed(texts)
        query_vec, chunk_vecs = vectors[-1], vectors[:-1]
        scored = [
            (cosine_similarity(query_vec, cv), row)
            for cv, row in zip(chunk_vecs, rows)
        ]

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = scored[:top_k]

    results: List[EvidenceResult] = []
    for score, row in top:
        evidence_id = row.get("evidence_id")
        if not evidence_id:
            # A chunk without a matching evidence row shouldn't normally
            # happen (ingest.py always creates both together), but skip
            # defensively rather than fabricate an evidence_id that
            # nothing else in the system knows about.
            logger.warning(
                "Chunk %s has no matching evidence row — skipping.", row.get("chunk_id")
            )
            continue
        results.append(
            EvidenceResult(
                evidence_id=evidence_id,
                content=row["content"],
                source_type=row.get("source_type") or "USER_PROVIDED",
                document_id=row.get("document_id"),
                document_page=row.get("page_number"),
                relevance_score=round(float(score), 4),
            )
        )
    return results
