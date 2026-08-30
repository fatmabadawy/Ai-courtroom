"""
backend/app/api/background/trial_runner.py
────────────────────────────────────────────
FastAPI BackgroundTasks wrapper that runs the trial asynchronously.
The /trial/start endpoint returns HTTP 202 immediately, then this task
calls trial_service.start_trial() in the background.
"""
from __future__ import annotations

import asyncio

from backend.app.api.services import trial_service


async def run_trial_background(case_id: str, judge_profile: str = "balanced") -> None:
    """
    Entry point for FastAPI's BackgroundTasks.
    Delegates to trial_service which in turn calls the graph interface.
    """
    await trial_service.start_trial(case_id, judge_profile)
