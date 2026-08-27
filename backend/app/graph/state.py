"""
backend/app/graph/state.py
──────────────────────────
Verbatim copy of INTERFACES.md §4 CourtroomState TypedDict.

DEVIATION (flagged in implementation_plan.md, Open Question #4):
  Added import line:
      from backend.app.models.schemas import (...)
  The §4 snippet in INTERFACES.md omits this import; without it the file
  cannot execute.  No field names, types, or literals have been changed.

Node convention (every agent must follow this — INTERFACES.md §4):
    def node(state: CourtroomState) -> CourtroomState:
        ...
        return updated_state
"""

from typing import TypedDict, List, Dict, Optional

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
