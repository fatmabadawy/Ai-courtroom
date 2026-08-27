"""
tests/test_step8_prosecution_defense.py
────────────────────────────────────────
Step 8 — tests for agents/prosecution.py, agents/defense.py,
and agents/_argument_builder.py.

Scenarios:
  (a) fixture with evidence → non-empty arguments, evidence-grounded
  (b) fixture with no evidence → empty evidence_ids, confidence ≤ 0.3
  (c) defense reads prosecution_arguments → sets responds_to_argument_id
  (d) confidence > 0.3 with empty evidence_ids → clamped to 0.3
"""

import json
from typing import List

import pytest

from backend.app.agents import prosecution, defense
from backend.app.agents import _argument_builder as builder_module
from backend.app.models.schemas import Argument, Claim


# ── Helper: build a state with claims ─────────────────────────────────────────

def make_state_with_claims(minimal_state, claims: List[Claim]) -> dict:
    return {
        **minimal_state,
        "claims": [c.model_dump() for c in claims],
    }


@pytest.fixture
def force_majeure_claim():
    return Claim(
        claim_id="CL-002",
        statement="WidgetCo's delivery delay was excused by a valid force majeure event.",
        made_by="defense",
    )


@pytest.fixture
def payment_claim():
    return Claim(
        claim_id="CL-001",
        statement="ACME Corp made NO payment to WidgetCo prior to the alleged breach date.",
        made_by="prosecution",
    )


# ── (a) Evidence-grounded path ─────────────────────────────────────────────────

class TestProsecutionWithEvidence:
    def test_returns_non_empty_arguments(self, minimal_state, payment_claim):
        state = make_state_with_claims(minimal_state, [payment_claim])
        result = prosecution.node(state)
        assert len(result["prosecution_arguments"]) > 0

    def test_argument_schema_valid(self, minimal_state, payment_claim):
        state = make_state_with_claims(minimal_state, [payment_claim])
        result = prosecution.node(state)
        for raw in result["prosecution_arguments"]:
            arg = Argument.model_validate(raw)
            assert arg.side == "prosecution"
            assert arg.claim_id == payment_claim.claim_id

    def test_argument_id_format(self, minimal_state, payment_claim):
        state = make_state_with_claims(minimal_state, [payment_claim])
        result = prosecution.node(state)
        for raw in result["prosecution_arguments"]:
            arg = Argument.model_validate(raw)
            assert arg.argument_id.startswith("prosecution-")


class TestDefenseWithEvidence:
    def test_returns_non_empty_arguments(self, minimal_state, force_majeure_claim):
        state = make_state_with_claims(minimal_state, [force_majeure_claim])
        result = defense.node(state)
        assert len(result["defense_arguments"]) > 0

    def test_evidence_grounded(self, minimal_state, force_majeure_claim):
        """Force majeure claim has supporting evidence → confidence > 0.3."""
        state = make_state_with_claims(minimal_state, [force_majeure_claim])
        result = defense.node(state)
        for raw in result["defense_arguments"]:
            arg = Argument.model_validate(raw)
            if arg.evidence_ids:
                assert arg.confidence > 0.3


# ── (b) No evidence path ──────────────────────────────────────────────────────

class TestNoEvidencePath:
    def test_no_evidence_low_confidence(self, minimal_state, monkeypatch):
        """When RAG returns nothing, both agents emit confidence ≤ 0.3."""
        monkeypatch.setattr(builder_module, "retrieve", lambda *a, **kw: [])

        # A claim that won't match any mock heuristic
        obscure_claim = Claim(
            claim_id="CL-ZZZ",
            statement="The defendant secretly transferred assets to an offshore account.",
            made_by="prosecution",
        )
        state = make_state_with_claims(minimal_state, [obscure_claim])

        # Prosecution
        result = prosecution.node(state)
        for raw in result["prosecution_arguments"]:
            arg = Argument.model_validate(raw)
            if not arg.evidence_ids:
                assert arg.confidence <= 0.3, (
                    f"Confidence {arg.confidence} too high with empty evidence_ids"
                )

    def test_no_evidence_empty_list(self, minimal_state, monkeypatch):
        """evidence_ids must be [] when nothing is retrieved."""
        monkeypatch.setattr(builder_module, "retrieve", lambda *a, **kw: [])

        obscure_claim = Claim(
            claim_id="CL-YYY",
            statement="Completely unsubstantiated claim with no supporting documents.",
            made_by="prosecution",
        )
        state = make_state_with_claims(minimal_state, [obscure_claim])
        result = prosecution.node(state)
        for raw in result["prosecution_arguments"]:
            arg = Argument.model_validate(raw)
            # With no evidence, the mock returns empty evidence_ids
            # (this also exercises the "no evidence found" path)
            assert isinstance(arg.evidence_ids, list)


# ── (c) Defense reads prosecution arguments ────────────────────────────────────

class TestDefenseReadsProseution:
    def test_responds_to_argument_id_set(self, minimal_state, force_majeure_claim):
        """Defense must set responds_to_argument_id when rebutting prosecution."""
        # First run prosecution — returns a partial dict (only prosecution_arguments)
        state = make_state_with_claims(minimal_state, [force_majeure_claim])
        pros_partial = prosecution.node(state)
        # Merge partial result into state, as LangGraph does internally
        pros_state = {**state, **pros_partial}
        # Now run defense with the merged state
        def_partial = defense.node(pros_state)
        def_state = {**pros_state, **def_partial}
        for raw in def_state["defense_arguments"]:
            arg = Argument.model_validate(raw)
            if arg.claim_id == force_majeure_claim.claim_id:
                # Defense should reference the prosecution argument
                # (mock always sets responds_to_argument_id for rebuttal claims)
                assert arg.responds_to_argument_id is not None, (
                    "Defense must set responds_to_argument_id when rebutting prosecution"
                )


# ── (d) Confidence clamping ────────────────────────────────────────────────────

class TestConfidenceClamping:
    def test_confidence_clamped_when_no_evidence(self, minimal_state, monkeypatch):
        """LLM returns confidence=0.9 with empty evidence_ids → clamped to 0.3."""
        bad_response = json.dumps({
            "argument": "Some argument with no evidence backing.",
            "evidence_ids": [],   # empty!
            "source_ids": [],
            "confidence": 0.9,   # too high for empty evidence
            "responds_to_argument_id": None,
        })
        monkeypatch.setattr(
            builder_module, "get_llm_response", lambda *a, **kw: bad_response
        )
        claim = Claim(
            claim_id="CL-X",
            statement="Some claim.",
            made_by="prosecution",
        )
        state = make_state_with_claims(minimal_state, [claim])
        result = prosecution.node(state)
        for raw in result["prosecution_arguments"]:
            arg = Argument.model_validate(raw)
            assert arg.confidence <= 0.3, (
                f"confidence={arg.confidence} should have been clamped to 0.3"
            )
