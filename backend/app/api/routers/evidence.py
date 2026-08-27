"""
backend/app/api/routers/evidence.py
─────────────────────────────────────
GET /cases/{case_id}/evidence          — list all evidence for a case
GET /evidence/{evidence_id}            — single evidence item
GET /cases/{case_id}/evidence-graph    — React Flow node/edge payload
GET /cases/{case_id}/replay            — ordered agent message log
GET /cases/{case_id}/verdict           — latest verdict
GET /cases/{case_id}/verdicts          — all verdicts (history)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.database import adapter as db
from app.api.dependencies.auth import get_current_user
from app.api.services.evidence_service import build_evidence_graph, build_replay
from app.models.schemas import (
    EvidenceGraphResponse,
    ReplayResponse,
    Verdict,
)

router = APIRouter(tags=["evidence"])


@router.get("/cases/{case_id}/evidence")
async def list_evidence(
    case_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    case = await db.get_case(case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return await db.list_evidence(case_id)


@router.get("/evidence/{evidence_id}")
async def get_evidence(
    evidence_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    ev = await db.get_evidence(evidence_id)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    # Verify caller owns the parent case
    case = await db.get_case(ev["case_id"], current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return ev


@router.get("/cases/{case_id}/evidence-graph", response_model=EvidenceGraphResponse)
async def evidence_graph(
    case_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> EvidenceGraphResponse:
    """
    Returns node/edge JSON for React Flow.
    Graph is built server-side: Claim → Evidence → Source → Document
    """
    case = await db.get_case(case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return await build_evidence_graph(case_id)


@router.get("/cases/{case_id}/replay", response_model=ReplayResponse)
async def replay(
    case_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> ReplayResponse:
    """Returns agent events in true chronological order for the replay timeline."""
    case = await db.get_case(case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return await build_replay(case_id)


@router.get("/cases/{case_id}/verdict")
async def get_verdict(
    case_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    case = await db.get_case(case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    verdict = await db.get_latest_verdict(case_id)
    if not verdict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No verdict yet")
    return verdict


@router.get("/cases/{case_id}/verdicts")
async def list_verdicts(
    case_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    case = await db.get_case(case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return await db.list_verdicts(case_id)
