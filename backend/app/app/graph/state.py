"""
backend/app/graph/state.py
───────────────────────────
INTERFACES.md §4 — verbatim LangGraph state TypedDict.
OWNED BY MEMBER C. Member E copies this verbatim and reads it read-only.
Do NOT modify without team notice.
"""
from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

# These imports work once the full repo is assembled.
# During bootstrapping Member E also provides them via models/schemas.py.
try:
    from app.models.schemas import (
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
except ImportError:  # pragma: no cover
    # Fallback in case of import cycle during early development
    from typing import Any  # type: ignore
    Argument = Any  # type: ignore
    Claim = Any  # type: ignore
    CrossExaminationRound = Any  # type: ignore
    EvidenceQualityScore = Any  # type: ignore
    FactCheck = Any  # type: ignore
    HumanIntervention = Any  # type: ignore
    JudgeProfile = Any  # type: ignore
    Party = Any  # type: ignore
    Verdict = Any  # type: ignore


class CourtroomState(TypedDict):
    case_id: str
    case_description: str
    parties: List[Party]
    claims: List[Claim]
    legal_questions: List[str]
    evidence_ids: List[str]
    prosecution_arguments: List[Argument]
    defense_arguments: List[Argument]
    fact_checks: List[FactCheck]
    evidence_quality: Dict[str, EvidenceQualityScore]
    cross_examinations: List[CrossExaminationRound]
    unresolved_questions: List[str]
    human_intervention: Optional[HumanIntervention]
    judge_configuration: JudgeProfile
    verdict: Optional[Verdict]
    round: int
