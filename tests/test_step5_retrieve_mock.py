"""
tests/test_step5_retrieve_mock.py
──────────────────────────────────
Step 5 — verify rag/retrieve_mock.py and the retrieve() dispatch shim.
"""

import pytest

from backend.app.models.schemas import EvidenceResult
from backend.app.rag.retrieve_mock import retrieve as mock_retrieve
from backend.app.rag.retrieve import retrieve


class TestMockRetrieveDirect:
    """Test retrieve_mock.retrieve() directly."""

    def test_returns_list_of_evidence_results(self):
        results = mock_retrieve("case_001", "breach of contract")
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, EvidenceResult) for r in results)

    def test_all_fields_valid(self):
        for r in mock_retrieve("case_001", "force majeure"):
            assert r.evidence_id.startswith("EV-")
            assert 0.0 <= r.relevance_score <= 1.0
            assert r.source_type in (
                "USER_PROVIDED", "PUBLIC_LEGAL_SOURCE", "WEB_SOURCE", "SYNTHETIC"
            )

    def test_case_001_returns_fixture_ids(self):
        ids = {r.evidence_id for r in mock_retrieve("case_001", "any query")}
        assert "EV-001" in ids
        assert "EV-002" in ids
        assert "EV-003" in ids

    def test_unknown_case_returns_mock_pool(self):
        results = mock_retrieve("case_UNKNOWN", "any query")
        ids = {r.evidence_id for r in results}
        assert any(id_.startswith("EV-MOCK-") for id_ in ids)

    def test_top_k_caps_results(self):
        results = mock_retrieve("case_001", "any", top_k=1)
        assert len(results) <= 1

    def test_contradicting_evidence_present(self):
        """EV-MOCK-3 must be in the mock pool (used by fact-checker tests)."""
        pool = mock_retrieve("case_UNKNOWN", "payment", top_k=10)
        ids = {r.evidence_id for r in pool}
        assert "EV-MOCK-3" in ids, "EV-MOCK-3 (contradicting evidence) must be in pool"


class TestDispatchShim:
    """Test that retrieve() dispatches to mock when USE_MOCK_RAG=true."""

    def test_dispatch_to_mock(self):
        """conftest sets USE_MOCK_RAG=true — retrieve() must hit the mock."""
        results = retrieve("case_001", "contract clause")
        assert isinstance(results, list)
        assert all(isinstance(r, EvidenceResult) for r in results)

    def test_schema_valid_results(self):
        for r in retrieve("case_001", "force majeure"):
            # Round-trip through Pydantic to confirm all fields conform to schema
            re_validated = EvidenceResult.model_validate(r.model_dump())
            assert re_validated == r
