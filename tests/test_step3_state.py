"""
tests/test_step3_state.py
─────────────────────────
Step 3 — verify graph/state.py CourtroomState TypedDict.
"""

from backend.app.graph.state import CourtroomState
from backend.app.models.schemas import JudgeProfile


class TestCourtroomState:
    REQUIRED_KEYS = {
        "case_id",
        "case_description",
        "parties",
        "claims",
        "legal_questions",
        "evidence_ids",
        "prosecution_arguments",
        "defense_arguments",
        "fact_checks",
        "evidence_quality",
        "cross_examinations",
        "unresolved_questions",
        "human_intervention",
        "judge_configuration",
        "verdict",
        "round",
    }

    def test_all_keys_present(self):
        """CourtroomState must expose exactly the keys from INTERFACES.md §4."""
        actual = set(CourtroomState.__annotations__.keys())
        missing = self.REQUIRED_KEYS - actual
        extra = actual - self.REQUIRED_KEYS
        assert missing == set(), f"Missing keys: {missing}"
        assert extra == set(), f"Unexpected extra keys: {extra}"

    def test_construct_minimal_state(self, minimal_state):
        """A minimal state dict built from the fixture must be key-complete."""
        for key in self.REQUIRED_KEYS:
            assert key in minimal_state, f"minimal_state missing key: {key}"

    def test_node_convention_type_hint(self):
        """
        The node convention from §4 is:
            def node(state: CourtroomState) -> CourtroomState: ...
        Verify the type is importable and usable as an annotation.
        """

        def my_node(state: CourtroomState) -> CourtroomState:
            return state

        import inspect

        hints = inspect.get_annotations(my_node)
        assert hints["state"] is CourtroomState
        assert hints["return"] is CourtroomState
