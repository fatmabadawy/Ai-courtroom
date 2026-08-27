"""
tests/test_step11_full_graph.py
────────────────────────────────
Step 11 — full graph end-to-end test against fixture case_001.
Verifies that CL-001 → CONTRADICTED and CL-002 → SUPPORTED
propagate all the way through to the verdict.
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
FIXTURE_META = PROJECT_ROOT / "tests" / "fixtures" / "case_001" / "expected_results.json"


@pytest.fixture
def fixture_expected():
    with open(FIXTURE_META) as f:
        return json.load(f)["expected_results"]


class TestFullGraphEndToEnd:
    def test_fact_checks_match_expected(self, minimal_state, fixture_expected):
        """
        CL-001 must end up CONTRADICTED, CL-002 must end up SUPPORTED,
        all the way through the full graph.
        """
        from langgraph.checkpoint.memory import MemorySaver
        from backend.app.graph.build_graph import build_graph
        from backend.app.models.schemas import Claim

        # Seed state with the fixture claims
        claims = [
            Claim(
                claim_id="CL-001",
                statement="ACME Corp made NO payment to WidgetCo prior to the alleged breach date.",
                made_by="prosecution",
            ).model_dump(),
            Claim(
                claim_id="CL-002",
                statement="WidgetCo's delivery delay was excused by a valid force majeure event.",
                made_by="defense",
            ).model_dump(),
        ]
        state = {**minimal_state, "claims": claims}

        graph = build_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "case_001-e2e"}}
        result = graph.invoke(state, config=config)

        # Check fact_checks
        fact_check_map = {
            fc["claim_id"]: fc["status"]
            for fc in result.get("fact_checks", [])
        }
        for claim_id, expected_status in fixture_expected.items():
            actual = fact_check_map.get(claim_id)
            assert actual == expected_status, (
                f"claim_id={claim_id}: expected {expected_status}, got {actual}"
            )

    def test_verdict_non_none(self, minimal_state):
        from langgraph.checkpoint.memory import MemorySaver
        from backend.app.graph.build_graph import build_graph

        graph = build_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "case_001-verdict-check"}}
        result = graph.invoke(minimal_state, config=config)
        assert result.get("verdict") is not None

    def test_verdict_disclaimer_present(self, minimal_state):
        from langgraph.checkpoint.memory import MemorySaver
        from backend.app.graph.build_graph import build_graph

        graph = build_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "case_001-disclaimer"}}
        result = graph.invoke(minimal_state, config=config)
        verdict = result.get("verdict", {})
        assert "educational/research simulation" in verdict.get("disclaimer", "")

    def test_no_hallucinated_evidence_ids_in_verdict(self, minimal_state):
        from langgraph.checkpoint.memory import MemorySaver
        from backend.app.graph.build_graph import build_graph

        graph = build_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "case_001-hallucination"}}
        result = graph.invoke(minimal_state, config=config)

        verdict = result.get("verdict", {})
        valid_ids = set(result.get("evidence_ids", []))
        for eid in verdict.get("supporting_evidence_ids", []):
            assert eid in valid_ids, f"Hallucinated: {eid}"
        for eid in verdict.get("opposing_evidence_ids", []):
            assert eid in valid_ids, f"Hallucinated: {eid}"


class TestRunMockSchema:
    """Verify run_mock.py produces schema-valid output (unblocks Plan E)."""

    def test_run_mock_returns_valid_state(self):
        from backend.app.graph.run_mock import run_trial
        from backend.app.graph.state import CourtroomState

        state = run_trial("case_001")
        required_keys = set(CourtroomState.__annotations__.keys())
        missing = required_keys - set(state.keys())
        assert missing == set(), f"Mock state missing keys: {missing}"

    def test_run_mock_verdict_schema(self):
        from backend.app.graph.run_mock import run_trial
        from backend.app.models.schemas import Verdict

        state = run_trial("case_001")
        verdict = Verdict.model_validate(state["verdict"])
        assert "educational/research simulation" in verdict.disclaimer

    def test_run_mock_fact_checks_match_expected(self, fixture_expected):
        from backend.app.graph.run_mock import run_trial

        state = run_trial("case_001")
        fc_map = {fc["claim_id"]: fc["status"] for fc in state["fact_checks"]}
        for claim_id, expected in fixture_expected.items():
            assert fc_map.get(claim_id) == expected
