"""
backend/app/graph/run.py
─────────────────────────
Graph invocation interface — INTERFACES.md §7.

Public API (what Plan E codes against):
    run_trial(case_id: str) -> CourtroomState
    resume_trial(case_id: str, intervention: Optional[HumanIntervention]) -> CourtroomState

Checkpointing (PLAN_D):
  - Backed by Postgres when DATABASE_URL is set.
  - Falls back to LangGraph's in-memory MemorySaver when DATABASE_URL is unset
    or on import failure (follows same mock-flag pattern as USE_MOCK_RAG).

Human-in-the-loop (PLAN_D):
  - Uses LangGraph ≥ 0.2 interrupt() / Command pattern
    (DEVIATION #1: version-specific API, documented in implementation_plan.md).
  - Interrupt is raised by needs_human_input_node; resume sends a Command.

Mid-trial re-run (PLAN_D):
  - When new evidence arrives, only re-runs Prosecution/Defense/Fact-Check
    for claims flagged needs_reassessment in unresolved_questions.

USE_MOCK_GRAPH flag:
  - When true, delegates to graph/run_mock.py (for Plan E dev).
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.app.config import DATABASE_URL, USE_MOCK_GRAPH
from backend.app.graph.state import CourtroomState
from backend.app.models.schemas import HumanIntervention, JudgeProfile

logger = logging.getLogger(__name__)


# ── Checkpointer factory ───────────────────────────────────────────────────────

def _make_checkpointer():
    """
    Return a LangGraph checkpointer, backed by real persistent storage so a
    trial paused on human input (via `interrupt()` in build_graph.py) can
    actually be resumed later — a fresh `MemorySaver()` on every call would
    silently discard that paused state, since `run_trial` and `resume_trial`
    each construct their own checkpointer instance.

    - `postgresql://...` DATABASE_URL → Postgres checkpointer.
    - `sqlite:///...` DATABASE_URL (this project's default — see
      backend/app/database/client.py) → file-backed SqliteSaver pointed at
      the same on-disk file, so state survives across calls/process
      restarts.
    - Anything else / no DATABASE_URL → in-memory MemorySaver as a last
      resort. NOTE: this cannot support interrupt/resume across separate
      run_trial/resume_trial calls — it only works within a single
      long-lived process holding onto the same checkpointer instance.
    """
    if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            conn = PostgresSaver.from_conn_string(DATABASE_URL)
            conn.setup()  # creates checkpoint tables if they don't exist
            logger.info("Using Postgres checkpointer: %s", DATABASE_URL[:30] + "…")
            return conn
        except Exception as exc:
            logger.warning(
                "Postgres checkpointer unavailable (%s) — falling back to SqliteSaver.",
                exc,
            )

    if DATABASE_URL and DATABASE_URL.startswith("sqlite:///"):
        try:
            import sqlite3
            from pathlib import Path
            from langgraph.checkpoint.sqlite import SqliteSaver

            db_path = DATABASE_URL.removeprefix("sqlite:///") or "courtroom.sqlite3"
            checkpoint_path = str(Path(db_path).with_name(Path(db_path).stem + "_checkpoints.sqlite3"))
            conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
            saver = SqliteSaver(conn)
            saver.setup()
            logger.info("Using SQLite checkpointer: %s", checkpoint_path)
            return saver
        except Exception as exc:
            logger.warning(
                "SQLite checkpointer unavailable (%s) — falling back to MemorySaver "
                "(interrupt/resume will NOT work across separate calls).",
                exc,
            )

    from langgraph.checkpoint.memory import MemorySaver
    logger.warning(
        "Using in-memory MemorySaver — no DATABASE_URL set. "
        "Human-input interrupt/resume will NOT persist across separate calls."
    )
    return MemorySaver()


# ── Initial state factory ─────────────────────────────────────────────────────

def _initial_state(
    case_id: str,
    case_description: str,
    judge_profile: str = "balanced",
) -> CourtroomState:
    return {
        "case_id": case_id,
        "case_description": case_description,
        "parties": [],
        "claims": [],
        "legal_questions": [],
        "evidence_ids": [],
        "prosecution_arguments": [],
        "defense_arguments": [],
        "fact_checks": [],
        "evidence_quality": {},
        "cross_examinations": [],
        "unresolved_questions": [],
        "human_intervention": None,
        "judge_configuration": JudgeProfile(name=judge_profile),
        "verdict": None,
        "round": 1,
    }


# ── Case description loader ────────────────────────────────────────────────────

def _load_case_description(case_id: str) -> str:
    """
    Load case description text.

    Tries the real database first (any case created via POST /cases will be
    there). Falls back to a synthetic fixture for case_001 so tests and
    offline/demo runs work without a database — but a real DB row always
    takes precedence if one exists for that case_id.
    """
    import sqlite3
    from backend.app.database.client import database_path

    try:
        db_path = database_path()
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            try:
                cur = conn.execute(
                    "SELECT description FROM cases WHERE case_id = ?", (case_id,)
                )
                row = cur.fetchone()
                if row is not None:
                    return row[0]
            finally:
                conn.close()
    except Exception as exc:
        logger.warning("Could not read case_id=%r from database: %s", case_id, exc)

    _SYNTHETIC_CASES = {
        "case_001": (
            "ACME Corp v. WidgetCo — Breach of Supply Agreement. "
            "ACME Corp alleges WidgetCo materially breached a supply agreement by "
            "failing to deliver 10,000 Model-X widgets by March 31, 2024. "
            "WidgetCo contends delivery was excused by a force majeure event "
            "(government export controls on chip supplier Fab-Taiwan). "
            "A secondary dispute concerns whether ACME made a prepayment of "
            "$125,000 before the alleged breach date."
        ),
    }
    if case_id in _SYNTHETIC_CASES:
        return _SYNTHETIC_CASES[case_id]
    raise ValueError(
        f"case_id={case_id!r} not found in the database or synthetic fixtures. "
        "Create the case via POST /cases first, or use 'case_001' for tests."
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def run_trial(case_id: str) -> CourtroomState:
    """
    Build and run the full courtroom graph from scratch.

    Parameters
    ----------
    case_id: str — The case to run.

    Returns
    -------
    Final CourtroomState after the verdict is produced.
    """
    if USE_MOCK_GRAPH:
        from backend.app.graph.run_mock import run_trial as _mock_run
        return _mock_run(case_id)

    from backend.app.graph.build_graph import build_graph

    checkpointer = _make_checkpointer()
    graph = build_graph(checkpointer=checkpointer)

    case_description = _load_case_description(case_id)
    initial = _initial_state(case_id, case_description)

    config = {"configurable": {"thread_id": case_id}}

    logger.info("Starting trial: case_id=%r", case_id)

    try:
        final_state = graph.invoke(initial, config=config)
    except Exception as exc:
        logger.error("Unexpected error running trial: case_id=%r: %s", case_id, exc)
        raise

    if final_state.get("__interrupt__"):
        # LangGraph's interrupt() does not raise — it pauses the graph and
        # returns the current state with a "__interrupt__" key describing
        # why. Callers (e.g. E's trial_service) must check for this key and
        # call resume_trial() with a HumanIntervention to continue; treating
        # the presence of a verdict as the only "done" signal is not enough.
        logger.info(
            "Trial paused for human input: case_id=%r interrupt=%r",
            case_id,
            final_state["__interrupt__"],
        )
        return final_state

    logger.info(
        "Trial complete: case_id=%r verdict=%r",
        case_id,
        final_state.get("verdict", {}).get("finding") if final_state.get("verdict") else None,
    )
    return final_state


def resume_trial(
    case_id: str,
    intervention: Optional[HumanIntervention] = None,
) -> CourtroomState:
    """
    Resume a paused trial, optionally injecting a HumanIntervention.

    Parameters
    ----------
    case_id: str — The case to resume.
    intervention: HumanIntervention | None
        New evidence/affected claims provided by the human reviewer.
        If provided, claims whose claim_id is in intervention.affected_claim_ids
        are flagged for re-evaluation (mid-trial re-run logic).

    Returns
    -------
    Final CourtroomState after the verdict is produced.
    """
    if USE_MOCK_GRAPH:
        from backend.app.graph.run_mock import resume_trial as _mock_resume
        return _mock_resume(case_id, intervention)

    from langgraph.types import Command
    from backend.app.graph.build_graph import build_graph

    checkpointer = _make_checkpointer()
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": case_id}}

    # Build resume payload
    resume_state: dict = {}
    if intervention:
        resume_state["human_intervention"] = intervention.model_dump()
        # Flag affected claims for reassessment (mid-trial re-run, PLAN_D)
        resume_state["unresolved_questions"] = _flag_reassessment_claims(
            intervention.affected_claim_ids
        )

    logger.info("Resuming trial: case_id=%r intervention=%r", case_id, intervention)

    try:
        # LangGraph ≥ 0.2: send a Command with resume value
        final_state = graph.invoke(
            Command(resume=resume_state),
            config=config,
        )
    except Exception as exc:
        logger.error("resume_trial error for case_id=%r: %s", case_id, exc)
        raise

    return final_state


def _flag_reassessment_claims(affected_claim_ids: list[str]) -> list[str]:
    """
    Create unresolved_question entries that signal mid-trial re-run
    for the specified claims.
    """
    return [
        f"needs_reassessment: claim_id={cid!r} — new evidence injected by human reviewer"
        for cid in affected_claim_ids
    ]
