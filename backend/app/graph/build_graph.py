"""
backend/app/graph/build_graph.py
─────────────────────────────────
LangGraph graph definition.

Merge protocol (INTERFACES.md §5):
  C created this file (Phase 1) with:
      START → INTAKE → EVIDENCE → PARALLEL(PROSECUTION, DEFENSE) → PASSTHROUGH_STUB → END

  D replaced PASSTHROUGH_STUB with:
      FACT_CHECK → EVIDENCE_QUALITY → CROSS_EXAMINATION → conditional(NEEDS_HUMAN_INPUT) → JUDGE → END

Only node registrations (add_node / add_edge) live here.
All node *logic* lives in agents/*.py — this file stays small.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from backend.app.graph.state import CourtroomState

# ── Import node functions from their owners ────────────────────────────────────
from backend.app.agents.intake import node as intake_node
from backend.app.agents.prosecution import node as prosecution_node
from backend.app.agents.defense import node as defense_node
from backend.app.agents.fact_checker import node as fact_checker_node
from backend.app.agents.evidence_quality import node as evidence_quality_node
from backend.app.agents.cross_examiner import node as cross_examiner_node
from backend.app.agents.judge import node as judge_node

# ── Evidence retrieval node (owned by C — PLAN_C §"Graph skeleton") ───────────
from backend.app.rag.retrieve import retrieve as _retrieve
import logging

logger = logging.getLogger(__name__)


def evidence_node(state: CourtroomState) -> CourtroomState:
    """
    EVIDENCE node (C's responsibility):
    Given state["claims"] / state["legal_questions"], calls retrieve() and
    populates state["evidence_ids"] before Prosecution/Defense run.
    """
    case_id = state["case_id"]
    queries: list[str] = []
    for claim in state.get("claims", []):
        stmt = claim["statement"] if isinstance(claim, dict) else claim.statement
        queries.append(stmt)
    queries.extend(state.get("legal_questions", []))

    if not queries:
        queries = [state.get("case_description", "general evidence")]

    all_ids: set[str] = set(state.get("evidence_ids", []))  # preserve existing
    for q in queries:
        results = _retrieve(case_id, q)
        all_ids.update(r.evidence_id for r in results)

    logger.info("Evidence node: collected %d evidence IDs.", len(all_ids))
    return {**state, "evidence_ids": sorted(all_ids)}


def needs_human_input_node(state: CourtroomState) -> CourtroomState:
    """
    Passthrough node that exposes the human-intervention checkpoint.
    LangGraph's interrupt() is called here when the graph detects unresolved
    questions that require human input.  The actual interrupt/resume logic
    lives in graph/run.py.
    """
    # The interrupt call is issued by run.py's checkpointing wrapper.
    # This node itself just passes state through — the conditional edge below
    # decides whether to pause here.
    return state


# ── Conditional edge function ──────────────────────────────────────────────────

def _human_input_condition(state: CourtroomState) -> str:
    """
    Return "needs_human_input" if any unresolved questions are flagged,
    otherwise "judge".
    """
    if state.get("human_intervention") is not None:
        # Intervention already provided — proceed to judge
        return "judge"
    unresolved = state.get("unresolved_questions", [])
    if any("NEEDS_REVIEW" in q or "needs_reassessment" in q.lower() for q in unresolved):
        return "needs_human_input"
    return "judge"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_graph(checkpointer=None) -> StateGraph:
    """
    Build and compile the full courtroom graph.

    Parameters
    ----------
    checkpointer:
        A LangGraph checkpointer (e.g., MemorySaver or PostgresSaver).
        If None, the graph runs without persistence.

    Returns
    -------
    Compiled LangGraph StateGraph.
    """
    graph = StateGraph(CourtroomState)

    # ── C's nodes ─────────────────────────────────────────────────────────────
    graph.add_node("intake", intake_node)
    graph.add_node("evidence", evidence_node)
    graph.add_node("prosecution", prosecution_node)
    graph.add_node("defense", defense_node)

    # ── D's nodes ─────────────────────────────────────────────────────────────
    graph.add_node("fact_check", fact_checker_node)
    graph.add_node("evidence_quality", evidence_quality_node)
    graph.add_node("cross_examination", cross_examiner_node)
    graph.add_node("needs_human_input", needs_human_input_node)
    graph.add_node("judge", judge_node)

    # ── Edges ──────────────────────────────────────────────────────────────────
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "evidence")

    # Parallel branch: prosecution and defense run concurrently then merge
    graph.add_edge("evidence", "prosecution")
    graph.add_edge("evidence", "defense")

    # Both prosecution and defense merge into fact_check
    graph.add_edge("prosecution", "fact_check")
    graph.add_edge("defense", "fact_check")

    graph.add_edge("fact_check", "evidence_quality")
    graph.add_edge("evidence_quality", "cross_examination")

    # Conditional: human input or judge
    graph.add_conditional_edges(
        "cross_examination",
        _human_input_condition,
        {
            "needs_human_input": "needs_human_input",
            "judge": "judge",
        },
    )

    graph.add_edge("needs_human_input", "judge")
    graph.add_edge("judge", END)

    kwargs = {}
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer

    return graph.compile(**kwargs)
