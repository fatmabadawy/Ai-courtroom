"""
backend/app/agents/defense.py
──────────────────────────────
Defense Agent — Plan C.

Produces Argument objects for each claim/legal question from the
defense's perspective.  Logic is shared with prosecution.py via
agents._argument_builder (parameterized by side="defense").

Key enforcements (PLAN_C):
  - confidence > 0.3 requires non-empty evidence_ids (in-code, not just prompt).
  - Reads state["prosecution_arguments"] and sets responds_to_argument_id
    when directly rebutting a specific prosecution argument.
  - Each argument_id = f"defense-{claim_id}-r{round}" (DEVIATION #5).
  - Emits "no evidence found" gracefully.
"""

from __future__ import annotations

from backend.app.agents._argument_builder import build_arguments
from backend.app.graph.state import CourtroomState
from backend.app.models.schemas import Argument


def node(state: CourtroomState) -> CourtroomState:
    """
    Defense node: builds defense arguments, reading prosecution_arguments
    to set responds_to_argument_id on rebuttal arguments.

    Returns ONLY defense_arguments (not **state) so that LangGraph's
    parallel fan-in merge with prosecution does not raise
    InvalidUpdateError on shared keys.
    """
    prior_arguments = state.get("prosecution_arguments", [])
    arguments = build_arguments(
        state=state,
        side="defense",
        prior_arguments=prior_arguments,
    )
    return {
        "defense_arguments": [a.model_dump() for a in arguments],
    }
