"""
tests/test_human_interrupt.py
──────────────────────────────
Integration test for the human-in-the-loop interrupt/resume mechanics
(PLAN_D). Two bugs were found and fixed during integration:

  1. `needs_human_input_node` (build_graph.py) previously just passed state
     through without ever calling LangGraph's `interrupt()`, so the graph
     never actually paused for human review — it silently continued straight
     to judge regardless of unresolved NEEDS_REVIEW questions.
  2. `_make_checkpointer()` (run.py) minted a brand-new, empty
     `MemorySaver()` on every call. Even after fixing (1), a paused trial's
     state would be invisible to a later `resume_trial()` call, because
     each call got its own throwaway in-memory checkpointer instead of a
     persistent, shared one.

This test builds a minimal graph using the REAL `needs_human_input_node`,
`_human_input_condition`, and `judge.node` functions (not stubs) to prove
the full pause → resume → verdict path actually works end-to-end with a
single shared checkpointer, the way run.py now uses a persistent
(SQLite-backed, or MemorySaver-if-explicitly-shared) checkpointer rather
than one-off instances.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from backend.app.agents.judge import node as judge_node
from backend.app.graph.build_graph import needs_human_input_node, _human_input_condition
from backend.app.graph.state import CourtroomState
from backend.app.models.schemas import JudgeProfile


def _minimal_state(unresolved: list[str]) -> CourtroomState:
    return {
        "case_id": "case_TEST_INTERRUPT",
        "case_description": "Test case for interrupt mechanics.",
        "parties": [],
        "claims": [],
        "legal_questions": [],
        "evidence_ids": [],
        "prosecution_arguments": [],
        "defense_arguments": [],
        "fact_checks": [],
        "evidence_quality": {},
        "cross_examinations": [],
        "unresolved_questions": unresolved,
        "human_intervention": None,
        "judge_configuration": JudgeProfile(name="balanced"),
        "verdict": None,
        "round": 1,
    }


def _build_minimal_interrupt_graph(checkpointer):
    """
    A 2-node graph — needs_human_input → conditional(judge) — using the
    REAL functions from build_graph.py, so this test proves the actual
    production interrupt/resume wiring works, not a re-implementation of it.
    """
    graph = StateGraph(CourtroomState)
    graph.add_node("needs_human_input", needs_human_input_node)
    graph.add_node("judge", judge_node)
    graph.add_edge(START, "needs_human_input")
    graph.add_conditional_edges(
        "needs_human_input",
        _human_input_condition,
        {"needs_human_input": "needs_human_input", "judge": "judge"},
    )
    graph.add_edge("judge", END)
    return graph.compile(checkpointer=checkpointer)


class TestNeedsHumanInputNodeCallsInterrupt:
    def test_interrupt_is_invoked(self, monkeypatch):
        """Unit-level: the node must call interrupt(), not just pass state through."""
        called = {}

        def fake_interrupt(payload):
            called["payload"] = payload
            return None

        monkeypatch.setattr("backend.app.graph.build_graph.interrupt", fake_interrupt)
        state = _minimal_state(["NEEDS_REVIEW: something"])
        needs_human_input_node(state)
        assert "payload" in called, "needs_human_input_node did not call interrupt()"
        assert called["payload"]["unresolved_questions"] == ["NEEDS_REVIEW: something"]


class TestGraphActuallyPausesAndResumes:
    def test_full_pause_then_resume_reaches_verdict(self):
        """
        End-to-end with the real nodes and a single shared checkpointer:
          1. First invoke() pauses — no verdict, "__interrupt__" present.
          2. Command(resume=...) on the SAME checkpointer/thread_id
             completes the trial and produces a verdict.
        """
        checkpointer = MemorySaver()  # ONE shared instance — this is the fix
        graph = _build_minimal_interrupt_graph(checkpointer)
        config = {"configurable": {"thread_id": "case_TEST_INTERRUPT"}}

        initial = _minimal_state(["NEEDS_REVIEW: contested claim CL-001"])
        first = graph.invoke(initial, config=config)

        assert first.get("verdict") is None, "graph should have paused before reaching judge"
        assert first.get("__interrupt__"), "graph did not pause — interrupt() was not effective"

        resumed = graph.invoke(
            Command(resume={"new_document_ids": ["DOC-NEW-1"], "affected_claim_ids": ["CL-001"]}),
            config=config,
        )

        assert resumed.get("verdict") is not None, "resume did not reach the judge node"
        assert resumed.get("human_intervention") is not None

    def test_fresh_checkpointer_per_call_would_lose_the_pause(self):
        """
        Documents the bug directly: if each call gets its OWN fresh
        MemorySaver (the pre-fix behavior), resuming can't see the paused
        state at all — LangGraph has no record of thread_id under a
        checkpointer that never saw the first invoke().
        """
        thread_id = "case_TEST_INTERRUPT_ISOLATED"
        config = {"configurable": {"thread_id": thread_id}}

        graph_a = _build_minimal_interrupt_graph(MemorySaver())
        first = graph_a.invoke(
            _minimal_state(["NEEDS_REVIEW: x"]), config=config
        )
        assert first.get("__interrupt__")

        # A DIFFERENT checkpointer instance (simulating the old bug) has no
        # memory of this thread_id's paused state.
        graph_b = _build_minimal_interrupt_graph(MemorySaver())
        state_snapshot = graph_b.get_state(config)
        assert state_snapshot.values == {}, (
            "a fresh checkpointer should NOT see the other instance's paused state "
            "— this is exactly why run.py must reuse one persistent checkpointer"
        )
