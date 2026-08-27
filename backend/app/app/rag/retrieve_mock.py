"""
backend/app/rag/retrieve_mock.py
─────────────────────────────────
INTERFACES.md §6 — Mock RAG retrieve() for Member E to use before B ships the real thing.

Usage (controlled by USE_MOCK_RAG env var):
    if settings.USE_MOCK_RAG:
        from app.rag.retrieve_mock import retrieve
    else:
        from app.rag.retrieve import retrieve
"""
from __future__ import annotations

from typing import List, Optional

from app.models.schemas import EvidenceResult


def retrieve(
    case_id: str,
    query: str,
    top_k: int = 8,
    filters: Optional[dict] = None,
) -> List[EvidenceResult]:
    """
    Mock implementation of B's rag.retrieve() interface (INTERFACES.md §6).
    Returns hardcoded but schema-valid EvidenceResult objects.
    """
    results = [
        EvidenceResult(
            evidence_id="EV-MOCK-1",
            content="Sample contract clause: 'Delivery shall be completed no later "
                    "than 2024-03-01, failing which liquidated damages shall apply.'",
            source_type="SYNTHETIC",
            document_id="DOC-MOCK-1",
            document_page=1,
            relevance_score=0.9,
        ),
        EvidenceResult(
            evidence_id="EV-MOCK-2",
            content="Sample witness statement: 'I received the specification change "
                    "email on 2024-02-15, two weeks before the original deadline.'",
            source_type="SYNTHETIC",
            document_id="DOC-MOCK-2",
            document_page=2,
            relevance_score=0.8,
        ),
        EvidenceResult(
            evidence_id="EV-MOCK-3",
            content="Delivery log entry: 'Goods dispatched 2024-03-13. Recipient "
                    "confirmed receipt 2024-03-14.'",
            source_type="SYNTHETIC",
            document_id="DOC-MOCK-1",
            document_page=3,
            relevance_score=0.75,
        ),
    ]
    return results[:top_k]
