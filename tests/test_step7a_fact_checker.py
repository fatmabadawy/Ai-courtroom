"""
tests/test_step7a_fact_checker.py
──────────────────────────────────
Step 7a — standalone unit tests for agents/fact_checker.py.
Run against hand-built fixture Claim lists without the graph.
"""

import json

import pytest

from backend.app.agents import fact_checker as fc_module
from backend.app.agents.fact_checker import check_claim, VALID_STATUSES
from backend.app.models.schemas import Claim, FactCheck


# ── Fixture claims ─────────────────────────────────────────────────────────────

@pytest.fixture
def contradicted_claim():
    return Claim(
        claim_id="CL-001",
        statement="ACME Corp made NO payment to WidgetCo prior to the alleged breach date.",
        made_by="prosecution",
    )


@pytest.fixture
def supported_claim():
    return Claim(
        claim_id="CL-002",
        statement="WidgetCo's delivery delay was excused by a valid force majeure event.",
        made_by="defense",
    )


@pytest.fixture
def unverified_claim():
    return Claim(
        claim_id="CL-003",
        statement="WidgetCo knowingly misled investors about the delivery timeline.",
        made_by="prosecution",
    )


# ── Core behaviour ─────────────────────────────────────────────────────────────

class TestFactCheckerStatusEnum:
    def test_contradicted_claim(self, contradicted_claim):
        fc = check_claim(contradicted_claim, "case_001")
        assert fc.status == "CONTRADICTED", (
            f"Expected CONTRADICTED for payment-denial claim, got {fc.status}"
        )

    def test_supported_claim(self, supported_claim):
        fc = check_claim(supported_claim, "case_001")
        assert fc.status == "SUPPORTED", (
            f"Expected SUPPORTED for force-majeure claim, got {fc.status}"
        )

    def test_unverified_claim(self, unverified_claim):
        fc = check_claim(unverified_claim, "case_001")
        assert fc.status in VALID_STATUSES

    def test_status_always_in_enum(self, contradicted_claim):
        """Even if LLM returns a garbage status, output must be in VALID_STATUSES."""
        import backend.app.agents.fact_checker as fcm
        def bad_llm(*a, **kw):
            return json.dumps({
                "claim_id": "CL-001",
                "status": "DEFINITELY_TRUE",  # invalid
                "supporting_evidence_ids": [],
                "contradicting_evidence_ids": [],
                "confidence": 0.5,
                "reasoning": "test",
            })
        import pytest
        # patch get_llm_response on the module
        orig = fcm.get_llm_response
        fcm.get_llm_response = bad_llm
        try:
            fc = check_claim(contradicted_claim, "case_001")
            assert fc.status in VALID_STATUSES
        finally:
            fcm.get_llm_response = orig


class TestFactCheckerIndependentRetrieval:
    def test_does_not_reuse_existing_ids(self, contradicted_claim, monkeypatch):
        """
        Fact checker must call retrieve() independently — it should call
        retrieve() with the claim statement, not rely on state evidence_ids.
        """
        retrieve_calls = []
        orig_retrieve = fc_module.retrieve

        def spy_retrieve(case_id, query, **kw):
            retrieve_calls.append((case_id, query))
            return orig_retrieve(case_id, query, **kw)

        monkeypatch.setattr(fc_module, "retrieve", spy_retrieve)
        check_claim(contradicted_claim, "case_001")
        assert len(retrieve_calls) == 1
        # The query should be the claim statement, not just an ID
        assert "payment" in retrieve_calls[0][1].lower()


class TestFactCheckerOutputSchema:
    def test_returns_fact_check_object(self, supported_claim):
        fc = check_claim(supported_claim, "case_001")
        assert isinstance(fc, FactCheck)

    def test_confidence_in_range(self, supported_claim):
        fc = check_claim(supported_claim, "case_001")
        assert 0.0 <= fc.confidence <= 1.0

    def test_reasoning_non_empty(self, supported_claim):
        fc = check_claim(supported_claim, "case_001")
        assert len(fc.reasoning) > 0

    def test_round_trip_serialisation(self, contradicted_claim):
        fc = check_claim(contradicted_claim, "case_001")
        reloaded = FactCheck.model_validate_json(fc.model_dump_json())
        assert reloaded.claim_id == fc.claim_id
        assert reloaded.status == fc.status


class TestFactCheckerErrorRecovery:
    def test_parse_error_returns_unverified(self, contradicted_claim, monkeypatch):
        """If LLM returns unparseable JSON, node must not crash."""
        import backend.app.agents.fact_checker as fcm
        monkeypatch.setattr(fcm, "get_llm_response", lambda *a, **kw: "NOT JSON AT ALL")
        fc = check_claim(contradicted_claim, "case_001")
        assert fc.status == "UNVERIFIED"
        assert fc.confidence == 0.0
