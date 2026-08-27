"""
backend/app/api/routers/trial.py
─────────────────────────────────
POST /trial/start      — start trial (async, returns 202)
GET  /trial/state      — poll trial status
POST /trial/intervene  — submit human intervention (pauses/resumes)
POST /trial/resume     — resume after intervention
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.background.trial_runner import run_trial_background
from app.api.database import adapter as db
from app.api.dependencies.auth import get_current_user
from app.api.services.trial_service import resume_trial_service
from app.models.schemas import (
    InterventionRequest,
    StartTrialRequest,
    TrialStateResponse,
    Verdict,
)

router = APIRouter(prefix="/trial", tags=["trial"])


@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
async def start_trial(
    body: StartTrialRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Kicks off the trial as an async background task.
    Returns 202 immediately — poll /trial/state for updates.
    Uses mock graph when USE_MOCK_GRAPH=true.
    """
    case = await db.get_case(body.case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    current = await db.get_trial_status(body.case_id)
    if current and current["status"] == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trial is already running for this case",
        )

    await db.upsert_trial_status(body.case_id, "pending")
    background_tasks.add_task(run_trial_background, body.case_id, body.judge_profile)

    return {
        "case_id": body.case_id,
        "status": "pending",
        "message": "Trial started. Poll /trial/state?case_id={case_id} for updates.",
    }


@router.get("/state", response_model=TrialStateResponse)
async def get_trial_state(
    case_id: str = Query(..., description="The case ID to poll"),
    current_user: Dict[str, str] = Depends(get_current_user),
) -> TrialStateResponse:
    """Poll the current status and round of a trial."""
    case = await db.get_case(case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    trial = await db.get_trial_status(case_id)
    if not trial:
        return TrialStateResponse(case_id=case_id, status="pending")

    verdict = None
    if trial.get("state_snapshot") and trial["state_snapshot"].get("verdict"):
        verdict_data = trial["state_snapshot"]["verdict"]
        if isinstance(verdict_data, dict):
            verdict = Verdict(**verdict_data)

    return TrialStateResponse(
        case_id=case_id,
        status=trial["status"],
        round=trial.get("round", 0),
        verdict=verdict,
        state_snapshot=trial.get("state_snapshot"),
    )


@router.post("/intervene", status_code=status.HTTP_202_ACCEPTED)
async def intervene(
    body: InterventionRequest,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Submit a human intervention (new documents / affected claims).
    This pauses the current trial and marks it for resumption.
    """
    case = await db.get_case(body.case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    await db.upsert_trial_status(body.case_id, "paused")
    # Store the intervention in the snapshot so resume_trial can pick it up
    current = await db.get_trial_status(body.case_id) or {}
    snapshot = current.get("state_snapshot") or {}
    intervention_data = body.intervention.model_dump()
    snapshot["human_intervention"] = intervention_data
    await db.upsert_trial_status(body.case_id, "paused", current.get("round", 0), snapshot)

    return {"case_id": body.case_id, "status": "paused", "message": "Intervention recorded. Call /trial/resume to continue."}


@router.post("/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_trial(
    body: StartTrialRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Resume a paused trial, optionally applying a stored intervention."""
    case = await db.get_case(body.case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    trial = await db.get_trial_status(body.case_id)
    if not trial or trial["status"] not in ("paused", "error"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trial is not in a resumable state",
        )

    background_tasks.add_task(_resume_background, body.case_id)
    return {"case_id": body.case_id, "status": "running", "message": "Trial resumed."}


async def _resume_background(case_id: str) -> None:
    """Load stored intervention from snapshot and resume the trial."""
    trial = await db.get_trial_status(case_id)
    snapshot = (trial or {}).get("state_snapshot") or {}
    intervention_data = snapshot.get("human_intervention")
    intervention = None
    if intervention_data:
        from app.models.schemas import HumanIntervention
        intervention = HumanIntervention(**intervention_data)
    await resume_trial_service(case_id, intervention)
