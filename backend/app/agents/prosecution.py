"""
backend/app/agents/prosecution.py
───────────────────────────────────
Prosecution Agent — Plan C.

Produces Argument objects for each claim/legal question from the
prosecution's perspective.  Logic is shared with defense.py via
agents._argument_builder (parameterized by side="prosecution").

Key enforcements (PLAN_C):
  - confidence > 0.3 requires non-empty evidence_ids (in-code, not just prompt).
  - Each argument_id = f"prosecution-{claim_id}-r{round}" (DEVIATION #5).
  - Emits "no evidence found" gracefully (empty evidence_ids, low confidence).
"""

from __future__ import annotations

from backend.app.agents._argument_builder import build_arguments
from backend.app.graph.state import CourtroomState
from backend.app.models.schemas import Argument


def node(state: CourtroomState) -> CourtroomState:
    """
    Prosecution node: builds prosecution arguments for all claims.
    Populates state["prosecution_arguments"].
    """
    arguments = build_arguments(
        state=state,
        side="prosecution",
        prior_arguments=None,  # prosecution has no prior side to rebut
    )
    return {
        "prosecution_arguments": [a.model_dump() for a in arguments],
    }
