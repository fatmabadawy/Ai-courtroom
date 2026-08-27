"""
backend/app/rag/retrieve.py
───────────────────────────
Dispatch shim — delegates to retrieve_mock.py or the real B implementation
based on the USE_MOCK_RAG env flag.

Agents always import from here:
    from backend.app.rag.retrieve import retrieve

Swapping to B's real implementation = set USE_MOCK_RAG=false.
"""

from typing import List, Optional

from backend.app.config import USE_MOCK_RAG
from backend.app.models.schemas import EvidenceResult


def retrieve(
    case_id: str,
    query: str,
    top_k: int = 8,
    filters: Optional[dict] = None,
) -> List[EvidenceResult]:
    """
    Retrieve evidence for a given query.

    Delegates to the mock or real implementation based on USE_MOCK_RAG.
    Signature matches INTERFACES.md §6 exactly.
    """
    if USE_MOCK_RAG:
        from backend.app.rag.retrieve_mock import retrieve as _mock_retrieve
        return _mock_retrieve(case_id, query, top_k, filters)

    # Real B implementation — import here so the mock path never requires it.
    try:
        from backend.app.rag.retrieve_real import retrieve as _real_retrieve  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "USE_MOCK_RAG=false but backend/app/rag/retrieve_real.py does not exist. "
            "Either set USE_MOCK_RAG=true or wait for B's implementation."
        ) from exc

    return _real_retrieve(case_id, query, top_k, filters)
