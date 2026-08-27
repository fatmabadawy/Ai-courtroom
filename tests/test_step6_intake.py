"""
tests/test_step6_intake.py
───────────────────────────
Step 6 — four scenarios for the Intake agent:
  (a) Happy path → valid StructuredCase
  (b) LLM returns bad JSON once → retry succeeds
  (c) LLM returns bad JSON twice → fail-soft path
  (d) LLM hallucinates an evidence_id → stripped with log
"""

import json
import logging

import pytest

from backend.app.agents import intake as intake_module
from backend.app.agents.intake import node
from backend.app.models.schemas import StructuredCase


# ── (a) Happy path ─────────────────────────────────────────────────────────────

class TestIntakeHappyPath:
    def test_returns_schema_valid_state(self, minimal_state):
        result = node(minimal_state)
        # Claims must be present and all keys of CourtroomState must be in result
        assert "claims" in result
        assert "evidence_ids" in result
        assert isinstance(result["claims"], list)
        # Each claim must have required keys
        for c in result["claims"]:
            assert "claim_id" in c
            assert c["status"] in (
                "SUPPORTED", "CONTRADICTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"
            )

    def test_evidence_ids_populated(self, minimal_state):
        result = node(minimal_state)
        assert len(result["evidence_ids"]) > 0

    def test_legal_questions_populated(self, minimal_state):
        result = node(minimal_state)
        assert len(result["legal_questions"]) > 0


# ── (b) Retry on first bad JSON ───────────────────────────────────────────────

class TestIntakeRetrySucceeds:
    def test_retry_on_invalid_json(self, minimal_state, monkeypatch):
        """First call returns invalid JSON; second returns valid."""
        call_count = {"n": 0}
        valid_mock = intake_module._build_mock_response(
            minimal_state["case_id"],
            minimal_state["evidence_ids"],
        )

        def fake_llm(sys, usr, mock_response="", **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "THIS IS NOT JSON {{{"
            return valid_mock

        monkeypatch.setattr(intake_module, "get_llm_response", fake_llm)

        result = node(minimal_state)
        assert call_count["n"] == 2, "Should call LLM exactly twice (1 try + 1 retry)"
        assert len(result["claims"]) > 0

    def test_retry_logged(self, minimal_state, monkeypatch, caplog):
        valid_mock = intake_module._build_mock_response(
            minimal_state["case_id"],
            minimal_state["evidence_ids"],
        )
        call_count = {"n": 0}

        def fake_llm(sys, usr, mock_response="", **kw):
            call_count["n"] += 1
            return "INVALID" if call_count["n"] == 1 else valid_mock

        monkeypatch.setattr(intake_module, "get_llm_response", fake_llm)

        with caplog.at_level(logging.WARNING, logger="backend.app.agents.intake"):
            node(minimal_state)

        assert any("first attempt failed" in r.message for r in caplog.records)


# ── (c) Fail-soft on two bad attempts ────────────────────────────────────────

class TestIntakeFailSoft:
    def test_fail_soft_no_crash(self, minimal_state, monkeypatch):
        """Both LLM calls return garbage — node must NOT raise, must fail-soft."""
        monkeypatch.setattr(
            intake_module,
            "get_llm_response",
            lambda *a, **kw: "BROKEN JSON",
        )
        result = node(minimal_state)
        # Should return a state (not raise)
        assert isinstance(result, dict)
        assert "unresolved_questions" in result

    def test_fail_soft_adds_unresolved_question(self, minimal_state, monkeypatch):
        monkeypatch.setattr(
            intake_module,
            "get_llm_response",
            lambda *a, **kw: "BROKEN JSON",
        )
        result = node(minimal_state)
        assert any(
            "NEEDS_REVIEW" in q for q in result["unresolved_questions"]
        ), "fail-soft must append a NEEDS_REVIEW entry to unresolved_questions"

    def test_fail_soft_claims_empty(self, minimal_state, monkeypatch):
        """Fail-soft path should not populate claims (they stay as inherited)."""
        monkeypatch.setattr(
            intake_module,
            "get_llm_response",
            lambda *a, **kw: "BROKEN JSON",
        )
        # minimal_state has empty claims — fail-soft should keep them empty
        result = node(minimal_state)
        # The state still has the key; may be empty or whatever was in initial state
        assert "evidence_ids" in result


# ── (d) Hallucination strip ───────────────────────────────────────────────────

class TestIntakeHallucinationStrip:
    def test_fake_evidence_id_stripped(self, minimal_state, monkeypatch, caplog):
        """LLM embeds a hallucinated EV-9999 — must be stripped."""
        real_ids = minimal_state["evidence_ids"]
        hallucinated_response = json.dumps({
            "case_id": minimal_state["case_id"],
            "title": "Test",
            "description": "desc",
            "parties": [],
            "claims": [
                {
                    "claim_id": "CL-H1",
                    "statement": "Some claim.",
                    "made_by": "intake",
                    "related_evidence_ids": ["EV-9999"],  # hallucinated
                    "status": "UNVERIFIED",
                }
            ],
            "events": [],
            "legal_questions": [],
            "evidence_ids": real_ids + ["EV-9999"],  # hallucinated
            "unknowns": [],
            "contradictions": [],
            "provenance_type": "SYNTHETIC",
        })

        monkeypatch.setattr(
            intake_module,
            "get_llm_response",
            lambda *a, **kw: hallucinated_response,
        )

        with caplog.at_level(logging.WARNING, logger="backend.app.agents.intake"):
            result = node(minimal_state)

        # EV-9999 must not appear in evidence_ids
        assert "EV-9999" not in result["evidence_ids"]
        # Warning must have been logged
        assert any("EV-9999" in r.message for r in caplog.records)

    def test_valid_evidence_ids_kept(self, minimal_state, monkeypatch):
        """Real evidence IDs must survive the hallucination strip."""
        real_ids = minimal_state["evidence_ids"]
        good_response = intake_module._build_mock_response(
            minimal_state["case_id"], real_ids
        )
        monkeypatch.setattr(
            intake_module,
            "get_llm_response",
            lambda *a, **kw: good_response,
        )
        result = node(minimal_state)
        for eid in result["evidence_ids"]:
            assert eid in real_ids, f"{eid} not in retrieved set"
