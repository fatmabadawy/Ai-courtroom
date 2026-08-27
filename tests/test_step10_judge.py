"""
tests/test_step10_judge.py
──────────────────────────
Step 10 — tests for agents/judge.py.

Scenarios:
  (a) All cited IDs valid → verdict produced with full fields
  (b) LLM hallucinates an evidence_id → removed, flagged in unresolved_questions
  (c) All three profiles → produce Verdict with distinct judge_profile fields
  (d) Disclaimer always present
  (e) Confidence always in [0, 1]
"""

import json

import pytest

from backend.app.agents import judge as judge_module
from backend.app.agents.judge import deliberate
from backend.app.models.schemas import JudgeProfile, Verdict


@pytest.fixture
def full_state(minimal_state):
    """A state with all fields populated for the judge to consume."""
    state = dict(minimal_state)
    state["fact_checks"] = [
        {
            "claim_id": "CL-001",
            "status": "CONTRADICTED",
            "supporting_evidence_ids": [],
            "contradicting_evidence_ids": ["EV-002"],
            "confidence": 0.88,
            "reasoning": "Prepayment contradicts the claim.",
        },
        {
            "claim_id": "CL-002",
            "status": "SUPPORTED",
            "supporting_evidence_ids": ["EV-001", "EV-002", "EV-003"],
            "contradicting_evidence_ids": [],
            "confidence": 0.85,
            "reasoning": "Force majeure supported by contract and expert testimony.",
        },
    ]
    state["prosecution_arguments"] = [
        {
            "argument_id": "prosecution-CL-001-r1",
            "claim_id": "CL-001",
            "argument": "WidgetCo breached the contract.",
            "evidence_ids": ["EV-001"],
            "source_ids": [],
            "confidence": 0.65,
            "side": "prosecution",
            "round": 1,
            "responds_to_argument_id": None,
        }
    ]
    state["defense_arguments"] = [
        {
            "argument_id": "defense-CL-002-r1",
            "claim_id": "CL-002",
            "argument": "Force majeure excuses the delay.",
            "evidence_ids": ["EV-001", "EV-002", "EV-003"],
            "source_ids": [],
            "confidence": 0.85,
            "side": "defense",
            "round": 1,
            "responds_to_argument_id": None,
        }
    ]
    state["cross_examinations"] = []
    state["evidence_quality"] = {
        "EV-001": {
            "evidence_id": "EV-001",
            "reliability": 0.85,
            "directness": 0.80,
            "relevance": 0.90,
            "corroboration": 0.70,
            "recency": 0.75,
            "composite_score": 0.82,
            "methodology_version": "v1",
        }
    }
    return state


# ── (a) Happy path ─────────────────────────────────────────────────────────────

class TestJudgeHappyPath:
    def test_returns_verdict_object(self, full_state):
        verdict = deliberate(full_state, "balanced")
        assert isinstance(verdict, Verdict)

    def test_finding_non_empty(self, full_state):
        verdict = deliberate(full_state, "balanced")
        assert len(verdict.finding) > 0

    def test_reasoning_non_empty(self, full_state):
        verdict = deliberate(full_state, "balanced")
        assert len(verdict.reasoning) > 0

    def test_confidence_in_range(self, full_state):
        verdict = deliberate(full_state, "balanced")
        assert 0.0 <= verdict.confidence <= 1.0

    def test_round_trip_serialisation(self, full_state):
        verdict = deliberate(full_state, "balanced")
        reloaded = Verdict.model_validate_json(verdict.model_dump_json())
        assert reloaded.finding == verdict.finding


# ── (b) Hallucinated evidence_id removed ──────────────────────────────────────

class TestHallucinationGuard:
    def test_hallucinated_id_removed(self, full_state, monkeypatch):
        """LLM cites EV-9999 which is not in state['evidence_ids'] — must be removed."""
        valid_ids = list(full_state["evidence_ids"])
        bad_response = json.dumps({
            "finding": "For the defendant",
            "supporting_evidence_ids": valid_ids + ["EV-9999"],  # hallucinated
            "opposing_evidence_ids": ["EV-FAKE"],                # hallucinated
            "unresolved_questions": [],
            "reasoning": "Based on all evidence.",
            "confidence": 0.8,
        })
        monkeypatch.setattr(judge_module, "get_llm_response", lambda *a, **kw: bad_response)

        verdict = deliberate(full_state, "balanced")
        assert "EV-9999" not in verdict.supporting_evidence_ids
        assert "EV-FAKE" not in verdict.opposing_evidence_ids

    def test_hallucinated_id_flagged_in_unresolved(self, full_state, monkeypatch):
        """Removed hallucinated IDs must be flagged in unresolved_questions."""
        valid_ids = list(full_state["evidence_ids"])
        bad_response = json.dumps({
            "finding": "For the plaintiff",
            "supporting_evidence_ids": ["EV-HALLUCINATED"],
            "opposing_evidence_ids": [],
            "unresolved_questions": [],
            "reasoning": "reason",
            "confidence": 0.7,
        })
        monkeypatch.setattr(judge_module, "get_llm_response", lambda *a, **kw: bad_response)

        verdict = deliberate(full_state, "balanced")
        assert any("EV-HALLUCINATED" in q for q in verdict.unresolved_questions)

    def test_valid_ids_kept(self, full_state):
        """Real evidence IDs must survive validation."""
        verdict = deliberate(full_state, "balanced")
        for eid in verdict.supporting_evidence_ids + verdict.opposing_evidence_ids:
            assert eid in full_state["evidence_ids"], f"{eid} not in evidence_ids"


# ── (c) Three profiles produce distinct output ────────────────────────────────

class TestJudgeProfiles:
    def test_all_three_profiles_produce_verdicts(self, full_state):
        for profile in ("strict", "balanced", "skeptical"):
            v = deliberate(full_state, profile)
            assert isinstance(v, Verdict)
            assert v.judge_profile == profile

    def test_profiles_have_distinct_judge_profile_field(self, full_state):
        profiles = {}
        for profile in ("strict", "balanced", "skeptical"):
            profiles[profile] = deliberate(full_state, profile)
        # Each verdict records its profile
        assert profiles["strict"].judge_profile == "strict"
        assert profiles["balanced"].judge_profile == "balanced"
        assert profiles["skeptical"].judge_profile == "skeptical"

    def test_profiles_produce_different_output(self, full_state):
        """Mock returns distinct finding/confidence per profile."""
        verdicts = {p: deliberate(full_state, p) for p in ("strict", "balanced", "skeptical")}
        # At least two should differ in confidence (mock gives 0.72, 0.81, 0.51)
        confidences = [v.confidence for v in verdicts.values()]
        assert len(set(confidences)) > 1, "All three profiles produced identical confidence"


# ── (d) Disclaimer ────────────────────────────────────────────────────────────

class TestDisclaimer:
    def test_disclaimer_always_present(self, full_state):
        for profile in ("strict", "balanced", "skeptical"):
            v = deliberate(full_state, profile)
            assert "educational/research simulation" in v.disclaimer
            assert "not legal advice" in v.disclaimer


# ── (e) Parse error recovery ──────────────────────────────────────────────────

class TestJudgeErrorRecovery:
    def test_parse_error_returns_undetermined(self, full_state, monkeypatch):
        monkeypatch.setattr(judge_module, "get_llm_response", lambda *a, **kw: "BROKEN")
        verdict = deliberate(full_state, "balanced")
        assert verdict.finding == "Undetermined"
        assert verdict.confidence == 0.0
