"""
backend/app/graph/run_mock.py
──────────────────────────────
INTERFACES.md §7 — Mock graph for Member E to use before C/D ship the real graph.
Provides schema-valid CourtroomState with a populated Verdict.

Usage (controlled by USE_MOCK_GRAPH env var):
    if settings.USE_MOCK_GRAPH:
        from backend.app.graph.run_mock import run_trial, resume_trial
    else:
        from backend.app.graph.run import run_trial, resume_trial
"""
from __future__ import annotations

import asyncio
from typing import Optional

from backend.app.graph.state import CourtroomState
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


def _build_mock_state(case_id: str) -> CourtroomState:
    """Return a hardcoded but schema-valid CourtroomState with a populated Verdict."""
    parties = [
        Party(
            party_id="P-001",
            name="Alice Corp",
            role="plaintiff",
            description="Claimant alleging breach of contract",
        ),
        Party(
            party_id="P-002",
            name="Bob Ltd",
            role="defendant",
            description="Respondent denying breach",
        ),
    ]

    claims = [
        Claim(
            claim_id="CL-001",
            statement="Bob Ltd failed to deliver goods by the agreed deadline.",
            made_by="prosecution",
            related_evidence_ids=["EV-MOCK-1"],
            status="SUPPORTED",
        ),
        Claim(
            claim_id="CL-002",
            statement="Alice Corp caused the delay by not providing specs on time.",
            made_by="defense",
            related_evidence_ids=["EV-MOCK-2"],
            status="PARTIALLY_SUPPORTED",
        ),
    ]

    prosecution_arguments = [
        Argument(
            claim_id="CL-001",
            argument="The contract explicitly states a delivery date of 2024-03-01 "
                     "which was not met.",
            evidence_ids=["EV-MOCK-1"],
            source_ids=["SRC-MOCK-1"],
            confidence=0.88,
            side="prosecution",
            round=1,
        )
    ]

    defense_arguments = [
        Argument(
            claim_id="CL-002",
            argument="Alice Corp's specification changes on 2024-02-15 constituted "
                     "a force majeure event.",
            evidence_ids=["EV-MOCK-2"],
            source_ids=["SRC-MOCK-2"],
            confidence=0.62,
            side="defense",
            round=1,
        )
    ]

    fact_checks = [
        FactCheck(
            claim_id="CL-001",
            status="SUPPORTED",
            supporting_evidence_ids=["EV-MOCK-1"],
            contradicting_evidence_ids=[],
            confidence=0.85,
            reasoning="Delivery log confirms goods arrived 12 days late.",
        ),
        FactCheck(
            claim_id="CL-002",
            status="PARTIALLY_SUPPORTED",
            supporting_evidence_ids=["EV-MOCK-2"],
            contradicting_evidence_ids=["EV-MOCK-1"],
            confidence=0.55,
            reasoning="Specification email exists but change impact is debatable.",
        ),
    ]

    evidence_quality: dict[str, EvidenceQualityScore] = {
        "EV-MOCK-1": EvidenceQualityScore(
            evidence_id="EV-MOCK-1",
            reliability=0.92,
            directness=0.88,
            relevance=0.95,
            corroboration=0.80,
            recency=0.70,
            composite_score=0.85,
        ),
        "EV-MOCK-2": EvidenceQualityScore(
            evidence_id="EV-MOCK-2",
            reliability=0.75,
            directness=0.60,
            relevance=0.80,
            corroboration=0.55,
            recency=0.65,
            composite_score=0.67,
        ),
    }

    cross_examinations = [
        CrossExaminationRound(
            round=1,
            challenger="cross_examiner",
            target_argument_id="CL-002",
            question="Can you show evidence that the spec change was communicated "
                     "before the original deadline?",
            response="The email was sent on 2024-02-15, two weeks before deadline.",
            outcome="weakened",
        )
    ]

    verdict = Verdict(
        finding="Partial liability: Bob Ltd bears primary responsibility for late "
                "delivery; Alice Corp's spec change is a mitigating factor.",
        supporting_evidence_ids=["EV-MOCK-1"],
        opposing_evidence_ids=["EV-MOCK-2"],
        unresolved_questions=[
            "Exact financial impact of the spec change",
            "Whether spec change qualifies as force majeure under contract terms",
        ],
        reasoning="The delivery log conclusively shows a delay. However, the spec "
                  "change email reduces Bob Ltd's full culpability.",
        confidence=0.78,
        judge_profile="balanced",
        disclaimer=(
            "This is an educational/research simulation and is not legal advice "
            "or a real legal decision-maker."
        ),
    )

    return CourtroomState(
        case_id=case_id,
        case_description="Contract dispute between Alice Corp and Bob Ltd.",
        parties=parties,
        claims=claims,
        legal_questions=[
            "Was the delivery deadline breached?",
            "Did the spec change constitute a valid force majeure event?",
        ],
        evidence_ids=["EV-MOCK-1", "EV-MOCK-2"],
        prosecution_arguments=prosecution_arguments,
        defense_arguments=defense_arguments,
        fact_checks=fact_checks,
        evidence_quality=evidence_quality,
        cross_examinations=cross_examinations,
        unresolved_questions=[
            "Exact financial impact of the spec change",
            "Whether spec change qualifies as force majeure under contract terms",
        ],
        human_intervention=None,
        judge_configuration=JudgeProfile(name="balanced"),
        verdict=verdict,
        round=1,
    )


async def run_trial(case_id: str) -> CourtroomState:
    """
    Mock implementation of graph.run.run_trial().
    Simulates async trial execution with a short delay.
    Returns a schema-valid CourtroomState.
    """
    await asyncio.sleep(0.1)  # simulate async work
    return _build_mock_state(case_id)


async def resume_trial(
    case_id: str,
    intervention: Optional[HumanIntervention] = None,
) -> CourtroomState:
    """
    Mock implementation of graph.run.resume_trial().
    Applies the intervention (if any) and returns an updated state.
    """
    await asyncio.sleep(0.1)
    state = _build_mock_state(case_id)
    if intervention:
        state["human_intervention"] = intervention
    return state
