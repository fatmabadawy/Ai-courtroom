"""
backend/app/models/schemas.py
──────────────────────────────
INTERFACES.md §3 — verbatim Pydantic schemas shared across all team members.
OWNED JOINTLY. Do NOT modify field names or types without team notice.

Member E creates this file because the repo was bootstrapped fresh.
When A/B/C/D arrive, they must use these exact definitions.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


# ── §3 verbatim schemas ──────────────────────────────────────────────────────

class Party(BaseModel):
    party_id: str
    name: str
    role: Literal["plaintiff", "defendant", "witness", "other"]
    description: Optional[str] = None


class CaseEvent(BaseModel):
    event_id: str
    description: str
    date: Optional[date] = None
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
    source_type: Literal[
        "USER_PROVIDED", "PUBLIC_LEGAL_SOURCE", "WEB_SOURCE", "SYNTHETIC"
    ]
    document_id: Optional[str] = None
    document_page: Optional[int] = None
    relevance_score: float


class Argument(BaseModel):
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
    status: Literal[
        "SUPPORTED", "CONTRADICTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"
    ]
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


# ── API-layer request/response models (Member E only) ────────────────────────
# These are NOT part of the shared contract — they are thin wrappers used only
# in the API layer to handle HTTP request/response shapes.

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[dict] = None


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class CreateCaseRequest(BaseModel):
    title: str
    description: str
    provenance_type: Literal[
        "USER_PROVIDED", "PUBLIC_LEGAL_SOURCE", "SYNTHETIC"
    ] = "USER_PROVIDED"


class CaseRow(BaseModel):
    """DB row shape for a case (what the adapter returns)."""
    case_id: str
    title: str
    description: str
    provenance_type: str
    owner_id: str
    created_at: str
    status: str = "pending"


class DocumentRow(BaseModel):
    document_id: str
    case_id: str
    filename: str
    content_type: str
    size_bytes: int
    upload_status: str
    created_at: str


class StartTrialRequest(BaseModel):
    case_id: str
    judge_profile: Literal["strict", "balanced", "skeptical"] = "balanced"


class TrialStateResponse(BaseModel):
    case_id: str
    status: Literal["pending", "running", "paused", "completed", "error"]
    round: int = 0
    verdict: Optional[Verdict] = None
    # Full CourtroomState is returned as a dict to keep the API schema stable
    # even as the state evolves (Members C/D may add keys).
    state_snapshot: Optional[dict] = None


class InterventionRequest(BaseModel):
    case_id: str
    intervention: HumanIntervention


class PublicSearchRequest(BaseModel):
    query: str
    jurisdiction: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    top_k: int = 5


# Evidence graph node/edge shapes ─────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    type: Literal["claim", "evidence", "source", "document"]
    label: str
    data: dict = {}


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None


class EvidenceGraphResponse(BaseModel):
    case_id: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# Replay ──────────────────────────────────────────────────────────────────────

class AgentMessage(BaseModel):
    message_id: str
    case_id: str
    agent_name: str
    event_type: str
    content: str
    evidence_refs: List[str] = []
    confidence: Optional[float] = None
    timestamp: str


class ReplayResponse(BaseModel):
    case_id: str
    events: List[AgentMessage]
