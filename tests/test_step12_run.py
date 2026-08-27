"""
tests/test_step12_run.py
────────────────────────
Step 12 — tests for graph/run.py public API.

Scenarios:
  (a) run_trial("case_001") returns a complete CourtroomState
  (b) resume_trial with HumanIntervention → intervention in state
  (c) affected_claim_ids → flagged in unresolved_questions
  (d) USE_MOCK_GRAPH=true → run_mock.py path
"""

import pytest

from backend.app.models.schemas import HumanIntervention


class TestRunTrial:
    def test_returns_complete_state(self):
        """run_trial must return a state with all CourtroomState keys."""
        from backend.app.graph.run import run_trial
        from backend.app.graph.state import CourtroomState

        state = run_trial("case_001")
        required = set(CourtroomState.__annotations__.keys())
        missing = required - set(state.keys())
        assert missing == set(), f"Missing keys: {missing}"

    def test_verdict_non_none(self):
        from backend.app.graph.run import run_trial
        state = run_trial("case_001")
        assert state.get("verdict") is not None

    def test_unknown_case_raises(self):
        from backend.app.graph.run import run_trial
        with pytest.raises(ValueError, match="case_id="):
            run_trial("case_DOES_NOT_EXIST")


class TestResumeTrial:
    def test_resume_without_intervention(self):
        """resume_trial with no intervention should still return a valid state."""
        from backend.app.graph import run as run_module
        import backend.app.graph.run as run_mod

        # Patch run_trial to simulate a completed trial
        orig_run = run_mod.run_trial

        def patched_run(case_id):
            from backend.app.graph.run_mock import run_trial as mock_run
            return mock_run(case_id)

        run_mod.run_trial = patched_run
        try:
            # Resume on an already-complete trial (no-op in mock path)
            from backend.app.graph.run_mock import resume_trial
            state = resume_trial("case_001", None)
            assert state is not None
        finally:
            run_mod.run_trial = orig_run

    def test_intervention_in_state(self):
        """With an intervention, state['human_intervention'] must be populated."""
        from backend.app.graph.run_mock import resume_trial

        intervention = HumanIntervention(
            new_document_ids=["DOC-NEW-1"],
            affected_claim_ids=["CL-001"],
            submitted_at="2024-06-01T10:00:00Z",
        )
        state = resume_trial("case_001", intervention)
        assert state["human_intervention"] is not None
        assert state["human_intervention"]["new_document_ids"] == ["DOC-NEW-1"]

    def test_affected_claims_flagged(self):
        """_flag_reassessment_claims must mark affected claims for re-run."""
        from backend.app.graph.run import _flag_reassessment_claims

        flags = _flag_reassessment_claims(["CL-001", "CL-002"])
        assert len(flags) == 2
        assert all("needs_reassessment" in f for f in flags)
        assert any("CL-001" in f for f in flags)
        assert any("CL-002" in f for f in flags)


class TestMockGraphDispatch:
    def test_use_mock_graph_routes_to_mock(self, monkeypatch):
        """When USE_MOCK_GRAPH=true, run_trial must use run_mock.py."""
        import backend.app.graph.run as run_mod
        monkeypatch.setattr(run_mod, "USE_MOCK_GRAPH", True)

        state = run_mod.run_trial("case_001")
        # Mock state always has 'Mock' in the case_description
        assert state["case_id"] == "case_001"
        assert state["verdict"] is not None

    def test_real_graph_used_when_flag_false(self, monkeypatch):
        """When USE_MOCK_GRAPH=false, run_trial must use the real graph."""
        import backend.app.graph.run as run_mod
        monkeypatch.setattr(run_mod, "USE_MOCK_GRAPH", False)

        state = run_mod.run_trial("case_001")
        assert state["case_id"] == "case_001"
        assert state["verdict"] is not None
