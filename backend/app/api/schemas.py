"""HTTP-only models owned by the API layer.

The shared domain models remain exclusively in :mod:`backend.app.models.schemas`, as
defined by INTERFACES.md §3.  Keeping transport shapes here prevents the API
from depending on the stale nested ``app/app`` package that was introduced by
the merge.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.app.models.schemas import HumanIntervention, Verdict


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
    case_id: str
    title: str
    description: str
    provenance_type: str
    owner_id: str
    created_at: str
    status: str = "pending"


class StartTrialRequest(BaseModel):
    case_id: str
    judge_profile: Literal["strict", "balanced", "skeptical"] = "balanced"


class TrialStateResponse(BaseModel):
    case_id: str
    status: Literal["pending", "running", "paused", "completed", "error"]
    round: int = 0
    verdict: Optional[Verdict] = None
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


class GraphNode(BaseModel):
    id: str
    type: Literal["claim", "evidence", "source", "document"]
    label: str
    data: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None


class EvidenceGraphResponse(BaseModel):
    case_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class AgentMessage(BaseModel):
    message_id: str
    case_id: str
    agent_name: str
    event_type: str
    content: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    timestamp: str


class ReplayResponse(BaseModel):
    case_id: str
    events: list[AgentMessage]
