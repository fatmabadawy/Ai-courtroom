"""
backend/app/graph/run_mock.py
──────────────────────────────
Mock graph runner — early deliverable for Plan E (INTERFACES.md §7).

Ships before the real graph is ready so E can start integration-testing
against a schema-valid CourtroomState + Verdict.

Same USE_MOCK_GRAPH=true flag pattern as USE_MOCK_RAG.
"""

from __future__ import annotations

from typing import Optional

from backend.app.models.schemas import (
    Argument,
    Claim,
    CrossExaminationRound,
    EvidenceQualityScore,
    FactCheck,
    HumanIntervention,
    JudgeProfile,
    Party,
    Verdict,
)


def _mock_state(case_id: str) -> dict:
    """Return a hardcoded but schema-valid CourtroomState with a populated Verdict."""
    parties = [
        Party(party_id="P1", name="ACME Corp", role="plaintiff"),
        Party(party_id="P2", name="WidgetCo", role="defendant"),
    ]
    claims = [
        Claim(
            claim_id="CL-001",
            statement="ACME Corp made NO payment to WidgetCo prior to the alleged breach date.",
            made_by="intake",
            related_evidence_ids=["EV-002"],
            status="CONTRADICTED",
        ),
        Claim(
            claim_id="CL-002",
            statement="WidgetCo's delay was excused by a valid force majeure event.",
            made_by="intake",
            related_evidence_ids=["EV-001", "EV-002", "EV-003"],
            status="SUPPORTED",
        ),
    ]
    evidence_ids = ["EV-001", "EV-002", "EV-003"]
    prosecution_args = [
        Argument(
            argument_id="prosecution-CL-001-r1",
            claim_id="CL-001",
            argument="The contract required delivery by March 31, 2024; WidgetCo failed.",
            evidence_ids=["EV-001"],
            confidence=0.65,
            side="prosecution",
        )
    ]
    defense_args = [
        Argument(
            argument_id="defense-CL-002-r1",
            claim_id="CL-002",
            argument="Force majeure (§9.3) excuses the delay; expert confirms.",
            evidence_ids=["EV-001", "EV-002", "EV-003"],
            confidence=0.85,
            side="defense",
            responds_to_argument_id="prosecution-CL-001-r1",
        )
    ]
    fact_checks = [
        FactCheck(
            claim_id="CL-001",
            status="CONTRADICTED",
            supporting_evidence_ids=[],
            contradicting_evidence_ids=["EV-002"],
            confidence=0.88,
            reasoning="Prepayment record contradicts the claim.",
        ),
        FactCheck(
            claim_id="CL-002",
            status="SUPPORTED",
            supporting_evidence_ids=["EV-001", "EV-002", "EV-003"],
            contradicting_evidence_ids=[],
            confidence=0.85,
            reasoning="Contract clause + witness statement support force majeure.",
        ),
    ]
    evidence_quality = {
        eid: EvidenceQualityScore(
            evidence_id=eid,
            reliability=0.85,
            directness=0.80,
            relevance=0.90,
            corroboration=0.70,
            recency=0.75,
            composite_score=0.82,
        )
        for eid in evidence_ids
    }
    cross_exams = [
        CrossExaminationRound(
            round=1,
            challenger="cross_examiner",
            target_argument_id="prosecution-CL-001-r1",
            question="Can you independently corroborate the claim of no prior payment?",
            response="No independent corroboration available.",
            outcome="weakened",
        )
    ]
    verdict = Verdict(
        finding="For the defendant",
        supporting_evidence_ids=["EV-001", "EV-002", "EV-003"],
        opposing_evidence_ids=[],
        unresolved_questions=["Damages quantum remains to be determined"],
        reasoning=(
            "The balance of evidence establishes a valid force majeure event. "
            "The prosecution's payment claim is directly contradicted by the "
            "email thread."
        ),
        confidence=0.81,
        judge_profile="balanced",
    )
    return {
        "case_id": case_id,
        "case_description": "Mock case description for Plan E development.",
        "parties": [p.model_dump() for p in parties],
        "claims": [c.model_dump() for c in claims],
        "legal_questions": [
            "Did WidgetCo materially breach the supply agreement?",
            "Is the force majeure clause in §9.3 applicable?",
        ],
        "evidence_ids": evidence_ids,
        "prosecution_arguments": [a.model_dump() for a in prosecution_args],
        "defense_arguments": [a.model_dump() for a in defense_args],
        "fact_checks": [fc.model_dump() for fc in fact_checks],
        "evidence_quality": {k: v.model_dump() for k, v in evidence_quality.items()},
        "cross_examinations": [r.model_dump() for r in cross_exams],
        "unresolved_questions": ["Damages quantum remains to be determined"],
        "human_intervention": None,
        "judge_configuration": JudgeProfile(name="balanced").model_dump(),
        "verdict": verdict.model_dump(),
        "round": 2,
    }


def run_trial(case_id: str) -> dict:
    """
    Mock implementation of run_trial.
    Returns a hardcoded but schema-valid CourtroomState with a populated Verdict.
    """
    return _mock_state(case_id)


def resume_trial(
    case_id: str,
    intervention: Optional[HumanIntervention] = None,
) -> dict:
    """
    Mock implementation of resume_trial.
    Returns the same mock state, with intervention injected if provided.
    """
    state = _mock_state(case_id)
    if intervention:
        state["human_intervention"] = intervention.model_dump()
    return state
