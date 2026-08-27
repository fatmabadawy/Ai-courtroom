"""
tests/test_step2_schemas.py
───────────────────────────
Step 2 — verify models/schemas.py matches INTERFACES.md §3 exactly
(plus the flagged argument_id addition).
"""

import json
from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.models.schemas import (
    Argument,
    CaseEvent,
    Claim,
    CrossExaminationRound,
    EvidenceQualityScore,
    EvidenceResult,
    FactCheck,
    HumanIntervention,
    JudgeProfile,
    Party,
    StructuredCase,
    Verdict,
)


# ── Instantiation round-trips ─────────────────────────────────────────────────

class TestParty:
    def test_valid(self):
        p = Party(party_id="P1", name="ACME Corp", role="plaintiff")
        assert p.party_id == "P1"
        assert p.role == "plaintiff"

    def test_invalid_role(self):
        with pytest.raises(ValidationError):
            Party(party_id="P1", name="X", role="judge")  # not in Literal


class TestClaim:
    def test_default_status(self):
        c = Claim(claim_id="CL-1", statement="Test.", made_by="intake")
        assert c.status == "UNVERIFIED"

    def test_all_status_values(self):
        for s in ("SUPPORTED", "CONTRADICTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"):
            Claim(claim_id="x", statement="y", made_by="intake", status=s)

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            Claim(claim_id="x", statement="y", made_by="intake", status="NEEDS_REVIEW")


class TestStructuredCase:
    def test_round_trip(self):
        sc = StructuredCase(
            case_id="c1",
            title="Test Case",
            description="desc",
            provenance_type="SYNTHETIC",
        )
        dumped = sc.model_dump_json()
        loaded = StructuredCase.model_validate_json(dumped)
        assert loaded.case_id == "c1"


class TestEvidenceResult:
    def test_valid(self):
        er = EvidenceResult(
            evidence_id="EV-1",
            content="Some content",
            source_type="SYNTHETIC",
            relevance_score=0.9,
        )
        assert er.evidence_id == "EV-1"


class TestArgument:
    def test_has_argument_id_field(self):
        """DEVIATION: argument_id must exist on Argument."""
        a = Argument(
            argument_id="prosecution-CL-1-r1",
            claim_id="CL-1",
            argument="The defendant breached.",
            evidence_ids=["EV-1"],
            confidence=0.8,
            side="prosecution",
        )
        assert a.argument_id == "prosecution-CL-1-r1"

    def test_side_literal(self):
        with pytest.raises(ValidationError):
            Argument(
                argument_id="x",
                claim_id="c",
                argument="y",
                evidence_ids=[],
                confidence=0.1,
                side="judge",  # invalid
            )

    def test_responds_to_optional(self):
        a = Argument(
            argument_id="a1",
            claim_id="c1",
            argument="rebuttal",
            evidence_ids=[],
            confidence=0.2,
            side="defense",
            responds_to_argument_id="prosecution-c1-r1",
        )
        assert a.responds_to_argument_id == "prosecution-c1-r1"


class TestFactCheck:
    def test_valid(self):
        fc = FactCheck(
            claim_id="CL-1",
            status="CONTRADICTED",
            supporting_evidence_ids=[],
            contradicting_evidence_ids=["EV-2"],
            confidence=0.9,
            reasoning="EV-2 directly contradicts the claim.",
        )
        assert fc.status == "CONTRADICTED"


class TestEvidenceQualityScore:
    def test_methodology_version_default(self):
        eqs = EvidenceQualityScore(
            evidence_id="EV-1",
            reliability=0.8,
            directness=0.7,
            relevance=0.9,
            corroboration=0.6,
            recency=0.5,
            composite_score=0.72,
        )
        assert eqs.methodology_version == "v1"


class TestCrossExaminationRound:
    def test_challenger_literal(self):
        cr = CrossExaminationRound(
            round=1,
            challenger="cross_examiner",
            target_argument_id="prosecution-CL-1-r1",
            question="How do you explain EV-2?",
            response="Force majeure applies.",
            outcome="unchanged",
        )
        assert cr.challenger == "cross_examiner"

    def test_invalid_challenger(self):
        with pytest.raises(ValidationError):
            CrossExaminationRound(
                round=1,
                challenger="judge",  # invalid
                target_argument_id="x",
                question="q",
                response="r",
                outcome="unchanged",
            )


class TestJudgeProfile:
    def test_three_profiles(self):
        for name in ("strict", "balanced", "skeptical"):
            jp = JudgeProfile(name=name)
            assert jp.name == name


class TestVerdict:
    def test_disclaimer_default(self):
        v = Verdict(
            finding="For the defense.",
            supporting_evidence_ids=["EV-3"],
            opposing_evidence_ids=["EV-2"],
            unresolved_questions=[],
            reasoning="Force majeure applies.",
            confidence=0.82,
            judge_profile="balanced",
        )
        assert "educational/research simulation" in v.disclaimer
        assert "not legal advice" in v.disclaimer

    def test_round_trip(self):
        v = Verdict(
            finding="For the plaintiff.",
            supporting_evidence_ids=["EV-1"],
            opposing_evidence_ids=[],
            unresolved_questions=["Question of damages"],
            reasoning="Breach established.",
            confidence=0.75,
            judge_profile="strict",
        )
        assert Verdict.model_validate_json(v.model_dump_json()).confidence == 0.75


class TestHumanIntervention:
    def test_valid(self):
        hi = HumanIntervention(
            new_document_ids=["DOC-5"],
            affected_claim_ids=["CL-1"],
            submitted_at="2024-06-01T10:00:00Z",
        )
        assert hi.new_document_ids == ["DOC-5"]
