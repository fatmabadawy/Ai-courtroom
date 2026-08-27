"""
backend/app/rag/retrieve_mock.py
─────────────────────────────────
Verbatim mock from INTERFACES.md §6, extended with EV-MOCK-3
(contradicting evidence) so the fact-checker test fixture has something
to contradict against.

This file is owned here (C/D territory) but follows B's spec.  When B ships
the real retrieve.py, this file stays as-is — agents import from
rag.retrieve, not directly from rag.retrieve_mock.
"""

from typing import List, Optional

from backend.app.models.schemas import EvidenceResult

# Full fixture pool.  retrieve() returns a slice of these based on top_k.
_MOCK_EVIDENCE: List[EvidenceResult] = [
    EvidenceResult(
        evidence_id="EV-MOCK-1",
        content=(
            "Sample contract clause: Section 9.3 — Force Majeure. "
            "Neither party shall be liable for delays caused by circumstances "
            "beyond their reasonable control, including government export controls."
        ),
        source_type="SYNTHETIC",
        document_id="DOC-MOCK-1",
        document_page=1,
        relevance_score=0.9,
    ),
    EvidenceResult(
        evidence_id="EV-MOCK-2",
        content=(
            "Sample witness line: 'I confirm the government export control notice "
            "FT-2024-EC-0291 is authentic and caused the delivery delay.'"
        ),
        source_type="SYNTHETIC",
        document_id="DOC-MOCK-2",
        document_page=2,
        relevance_score=0.8,
    ),
    # EV-MOCK-3 deliberately contradicts a prosecution claim for fact-checker tests.
    EvidenceResult(
        evidence_id="EV-MOCK-3",
        content=(
            "Email thread (internal): 'WidgetCo received ACME Corp prepayment of "
            "$125,000 on January 20, 2024 — this contradicts ACME's claim that no "
            "payment was made before the breach date.'"
        ),
        source_type="SYNTHETIC",
        document_id="DOC-MOCK-3",
        document_page=1,
        relevance_score=0.85,
    ),
]

# Real fixture evidence IDs (maps case_001 IDs to mock content).
_FIXTURE_EVIDENCE: List[EvidenceResult] = [
    EvidenceResult(
        evidence_id="EV-001",
        content=(
            "Contract: Section 9.3 — Force Majeure clause; Section 4.2 — delivery "
            "deadline March 31, 2024; Section 7.1 — payment terms USD 250,000."
        ),
        source_type="USER_PROVIDED",
        document_id="DOC-001",
        document_page=1,
        relevance_score=0.95,
    ),
    EvidenceResult(
        evidence_id="EV-002",
        content=(
            "Email thread: WidgetCo received ACME Corp prepayment of $125,000 on "
            "January 20, 2024. Force majeure notice drafted for Section 9.3. "
            "Chip supplier Fab-Taiwan halted shipments due to government export "
            "controls (notice FT-2024-EC-0291)."
        ),
        source_type="USER_PROVIDED",
        document_id="DOC-002",
        document_page=1,
        relevance_score=0.88,
    ),
    EvidenceResult(
        evidence_id="EV-003",
        content=(
            "Witness statement — Marcus Chen, CSCA #4421: confirms export control "
            "notice FT-2024-EC-0291 is authentic; delivery delay qualifies as force "
            "majeure; no commercially reasonable alternative supplier available "
            "within March 31, 2024 deadline."
        ),
        source_type="USER_PROVIDED",
        document_id="DOC-003",
        document_page=1,
        relevance_score=0.92,
    ),
]

# Index for fast lookup by evidence_id
_EVIDENCE_INDEX = {
    e.evidence_id: e for e in _MOCK_EVIDENCE + _FIXTURE_EVIDENCE
}


def retrieve(
    case_id: str,
    query: str,
    top_k: int = 8,
    filters: Optional[dict] = None,
) -> List[EvidenceResult]:
    """
    Mock implementation of B's rag.retrieve() interface (INTERFACES.md §6).

    Returns fixture evidence for case_001; falls back to the generic MOCK pool
    for any other case_id.  top_k caps the result list length.
    """
    if case_id == "case_001":
        pool = _FIXTURE_EVIDENCE
    else:
        pool = _MOCK_EVIDENCE

    # Apply a trivial filter (evidence_id key only) if provided.
    if filters and "evidence_id" in filters:
        pool = [e for e in pool if e.evidence_id == filters["evidence_id"]]

    return pool[:top_k]


def get_evidence_by_id(evidence_id: str) -> Optional[EvidenceResult]:
    """Utility: look up a single EvidenceResult by ID (used by fact_checker)."""
    return _EVIDENCE_INDEX.get(evidence_id)
