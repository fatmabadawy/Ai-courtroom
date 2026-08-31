"""
backend/app/api/services/trial_service.py
──────────────────────────────────────────
Orchestrates calls to the graph interface (mock → real).

Does NOT contain agent reasoning — it only delegates to:
  - graph.run_mock (when USE_MOCK_GRAPH=true)
  - graph.run      (when USE_MOCK_GRAPH=false, i.e. C/D's real module)

The single `_get_graph()` function is the swap point.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from backend.app.api.config import get_settings
from backend.app.api.database import adapter as db
from backend.app.graph.state import CourtroomState
from backend.app.models.schemas import HumanIntervention

settings = get_settings()


def _get_graph():
    """Return the correct graph module based on the env flag."""
    if settings.use_mock_graph:
        import backend.app.graph.run_mock as graph_module
    else:
        import backend.app.graph.run as graph_module  # type: ignore — C/D will ship this
    return graph_module


async def start_trial(case_id: str, judge_profile: str = "balanced") -> None:
    """
    Called by the background task runner.
    Sets trial status to 'running', calls run_trial, then persists the result.
    """
    await db.upsert_trial_status(case_id, "running", 0)
    await db.append_agent_message(
        case_id=case_id,
        agent_name="system",
        event_type="trial_started",
        content=f"Trial started with judge profile: {judge_profile}",
    )

    try:
        graph = _get_graph()
        # INTERFACES.md §7 defines synchronous graph functions.  Offload the
        # CPU/blocking graph invocation so FastAPI's event loop remains free.
        state: CourtroomState = await asyncio.to_thread(graph.run_trial, case_id)

        # A trial paused for human input (needs_human_input_node calling
        # LangGraph's interrupt()) returns normally from run_trial/invoke —
        # it does NOT raise. LangGraph surfaces this via a "__interrupt__"
        # key in the returned state rather than an exception. Detect it here
        # so a paused trial is recorded as "paused", not "completed".
        is_paused = bool(state.get("__interrupt__"))

        # Persist verdict if present
        if state.get("verdict"):
            verdict_dict = state["verdict"]
            if hasattr(verdict_dict, "model_dump"):
                verdict_dict = verdict_dict.model_dump()
            await db.save_verdict(case_id, verdict_dict)

        # Persist agent messages from state (for replay)
        await _persist_state_messages(case_id, state)

        await db.upsert_trial_status(
            case_id,
            "paused" if is_paused else "completed",
            state.get("round", 1),
            _state_to_dict(state),
        )
        if is_paused:
            await db.append_agent_message(
                case_id=case_id,
                agent_name="system",
                event_type="trial_paused",
                content="Trial paused — awaiting human input (unresolved questions flagged for review).",
            )
            return
        await db.append_agent_message(
            case_id=case_id,
            agent_name="system",
            event_type="trial_completed",
            content="Trial completed successfully.",
        )

    except Exception as exc:
        await db.upsert_trial_status(case_id, "error")
        await db.append_agent_message(
            case_id=case_id,
            agent_name="system",
            event_type="trial_error",
            content=f"Trial failed: {exc}",
        )
        raise


async def resume_trial_service(
    case_id: str,
    intervention: Optional[HumanIntervention] = None,
) -> CourtroomState:
    """Resume an interrupted trial, optionally injecting human intervention."""
    await db.upsert_trial_status(case_id, "running")
    graph = _get_graph()
    state: CourtroomState = await asyncio.to_thread(
        graph.resume_trial, case_id, intervention
    )

    if state.get("verdict"):
        verdict_dict = state["verdict"]
        if hasattr(verdict_dict, "model_dump"):
            verdict_dict = verdict_dict.model_dump()
        await db.save_verdict(case_id, verdict_dict)

    await _persist_state_messages(case_id, state)
    await db.upsert_trial_status(
        case_id,
        "completed",
        state.get("round", 1),
        _state_to_dict(state),
    )
    return state


def _state_to_dict(state: CourtroomState) -> dict:
    """Convert a CourtroomState to a JSON-serialisable dict."""
    import dataclasses

    result = {}
    for k, v in state.items():
        if k == "__interrupt__":
            # LangGraph injects this list of `Interrupt` dataclass instances
            # into the returned state when the graph pauses — it isn't part
            # of the CourtroomState schema itself, but we keep a JSON-safe
            # summary so the frontend can show *why* a trial is paused.
            result[k] = [
                dataclasses.asdict(item) if dataclasses.is_dataclass(item) else str(item)
                for item in v
            ]
        elif hasattr(v, "model_dump"):
            result[k] = v.model_dump()
        elif isinstance(v, list):
            result[k] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in v
            ]
        elif isinstance(v, dict):
            result[k] = {
                dk: (dv.model_dump() if hasattr(dv, "model_dump") else dv)
                for dk, dv in v.items()
            }
        else:
            result[k] = v
    return result


async def _persist_state_messages(case_id: str, state: CourtroomState) -> None:
    """Extract key events from the state and store them as agent_messages for replay."""
    # Prosecution arguments
    for arg in state.get("prosecution_arguments", []):
        d = arg.model_dump() if hasattr(arg, "model_dump") else arg
        await db.append_agent_message(
            case_id=case_id,
            agent_name="prosecution",
            event_type="argument",
            content=d.get("argument", ""),
            evidence_refs=d.get("evidence_ids", []),
            confidence=d.get("confidence"),
        )

    # Defense arguments
    for arg in state.get("defense_arguments", []):
        d = arg.model_dump() if hasattr(arg, "model_dump") else arg
        await db.append_agent_message(
            case_id=case_id,
            agent_name="defense",
            event_type="argument",
            content=d.get("argument", ""),
            evidence_refs=d.get("evidence_ids", []),
            confidence=d.get("confidence"),
        )

    # Fact checks
    for fc in state.get("fact_checks", []):
        d = fc.model_dump() if hasattr(fc, "model_dump") else fc
        await db.append_agent_message(
            case_id=case_id,
            agent_name="fact_checker",
            event_type="fact_check",
            content=d.get("reasoning", ""),
            evidence_refs=d.get("supporting_evidence_ids", []),
            confidence=d.get("confidence"),
        )

    # Cross-examinations
    for cx in state.get("cross_examinations", []):
        d = cx.model_dump() if hasattr(cx, "model_dump") else cx
        await db.append_agent_message(
            case_id=case_id,
            agent_name="cross_examiner",
            event_type="cross_examination",
            content=f"Q: {d.get('question')} | A: {d.get('response')} | Outcome: {d.get('outcome')}",
        )

    # Verdict
    if state.get("verdict"):
        d = state["verdict"]
        if hasattr(d, "model_dump"):
            d = d.model_dump()
        await db.append_agent_message(
            case_id=case_id,
            agent_name="judge",
            event_type="verdict",
            content=d.get("finding", ""),
            evidence_refs=d.get("supporting_evidence_ids", []),
            confidence=d.get("confidence"),
        )
