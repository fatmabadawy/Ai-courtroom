"""
backend/app/api/routers/n8n_internal.py
────────────────────────────────────────
Internal endpoints for n8n → FastAPI integration.
Uses a separate service-token (NOT user JWTs).
n8n never accesses the database or graph directly — it calls these endpoints.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.app.api.config import get_settings
from backend.app.api.database import adapter as db

settings = get_settings()
router = APIRouter(prefix="/internal", tags=["n8n-internal"])


def _verify_service_token(x_service_token: str = Header(..., alias="X-Service-Token")) -> None:
    """Simple service token auth for n8n internal routes."""
    if x_service_token != settings.n8n_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
        )


@router.get("/health", dependencies=[Depends(_verify_service_token)])
async def internal_health() -> Dict[str, str]:
    """n8n can call this to verify the API is reachable."""
    return {"status": "ok", "service": "ai-courtroom-api"}


@router.get("/cases/{case_id}/trial-status", dependencies=[Depends(_verify_service_token)])
async def get_trial_status_for_n8n(case_id: str) -> Dict[str, Any]:
    """Used by n8n workflows to check trial progress."""
    trial = await db.get_trial_status(case_id)
    if not trial:
        return {"case_id": case_id, "status": "not_started"}
    return {"case_id": case_id, "status": trial["status"], "round": trial.get("round", 0)}


@router.post("/cases/{case_id}/notify-new-evidence", dependencies=[Depends(_verify_service_token)])
async def notify_new_evidence(case_id: str, body: Dict[str, Any]) -> Dict[str, str]:
    """
    Called by n8n when it detects new public evidence.
    Stores a notification message so the UI can surface it.
    """
    case = await db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    await db.append_agent_message(
        case_id=case_id,
        agent_name="n8n",
        event_type="new_evidence_detected",
        content=body.get("summary", "New evidence detected by automated workflow"),
        evidence_refs=body.get("evidence_ids", []),
    )
    return {"status": "ok", "message": "Notification recorded"}
