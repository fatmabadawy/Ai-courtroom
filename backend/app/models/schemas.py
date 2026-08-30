"""
backend/app/models/schemas.py
─────────────────────────────
Verbatim copy of INTERFACES.md §3 Pydantic schemas.

DOCUMENTED DEVIATION (INTERFACES.md §3):
  `Argument` gains one additional field:
      argument_id: str
  Reason: `CrossExaminationRound.target_argument_id` and
  `Argument.responds_to_argument_id` both reference an argument identifier,
  but the §3 schema has no such field.  This is a purely additive change —
  no existing field name, type, or literal has been altered.
  Generation convention: f"{side}-{claim_id}-r{round}" at construction time
  (see agents/prosecution.py and agents/defense.py).

All other field names, types, and literals are exactly as written in §3.
Do not modify this file without team notice (INTERFACES.md §3 preamble).
"""

from typing import List, Optional, Literal
from datetime import date
import datetime
from pydantic import BaseModel


class Party(BaseModel):
    party_id: str
    name: str
    role: Literal["plaintiff", "defendant", "witness", "other"]
    description: Optional[str] = None


class CaseEvent(BaseModel):
    event_id: str
    description: str
    date: Optional[datetime.date] = None
    evidence_ids: List[str] = []


class Claim(BaseModel):
    claim_id: str
    statement: str
    made_by: Literal["prosecution", "defense", "intake"]
    related_evidence_ids: List[str] = []
    status: Literal[
        "SUPPORTED", "CONTRADICTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"
    ] = "UNVERIFIED"


class StructuredCase(BaseModel):
    case_id: str
    title: str
    description: str
    parties: List[Party] = []
    claims: List[Claim] = []
    events: List[CaseEvent] = []
    legal_questions: List[str] = []
    evidence_ids: List[str] = []
    unknowns: List[str] = []
    contradictions: List[str] = []
    provenance_type: Literal["USER_PROVIDED", "PUBLIC_LEGAL_SOURCE", "SYNTHETIC"]


class EvidenceResult(BaseModel):
    """What rag.retrieve() returns — B's output contract."""

    evidence_id: str
    content: str
    source_type: Literal["USER_PROVIDED", "PUBLIC_LEGAL_SOURCE", "WEB_SOURCE", "SYNTHETIC"]
    document_id: Optional[str] = None
    document_page: Optional[int] = None
    relevance_score: float


class Argument(BaseModel):
    # Documented INTERFACES.md §3 deviation.
    argument_id: str
    claim_id: str
    argument: str
    evidence_ids: List[str]
    source_ids: List[str] = []
    confidence: float
    side: Literal["prosecution", "defense"]
    round: int = 1
    responds_to_argument_id: Optional[str] = None


class FactCheck(BaseModel):
    claim_id: str
    status: Literal["SUPPORTED", "CONTRADICTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"]
    supporting_evidence_ids: List[str]
    contradicting_evidence_ids: List[str]
    confidence: float
    reasoning: str


class EvidenceQualityScore(BaseModel):
    evidence_id: str
    reliability: float
    directness: float
    relevance: float
    corroboration: float
    recency: float
    authenticity_notes: Optional[str] = None
    composite_score: float
    methodology_version: str = "v1"


class CrossExaminationRound(BaseModel):
    round: int
    challenger: Literal["cross_examiner"]
    target_argument_id: str
    question: str
    response: str
    outcome: Literal["strengthened", "weakened", "unchanged"]


class JudgeProfile(BaseModel):
    name: Literal["strict", "balanced", "skeptical"]


class Verdict(BaseModel):
    finding: str
    supporting_evidence_ids: List[str]
    opposing_evidence_ids: List[str]
    unresolved_questions: List[str]
    reasoning: str
    confidence: float
    judge_profile: str
    disclaimer: str = (
        "This is an educational/research simulation and is not legal advice "
        "or a real legal decision-maker."
    )


class HumanIntervention(BaseModel):
    new_document_ids: List[str]
    affected_claim_ids: List[str]
    submitted_at: str
