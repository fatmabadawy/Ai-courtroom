"""
tests/test_step4_graph_skeleton.py
────────────────────────────────────
Step 4 — verify the graph compiles and its node list matches spec.
"""

import pytest


class TestGraphCompiles:
    def test_build_graph_importable(self):
        from backend.app.graph.build_graph import build_graph
        assert callable(build_graph)

    def test_graph_compiles_with_memory_saver(self):
        from langgraph.checkpoint.memory import MemorySaver
        from backend.app.graph.build_graph import build_graph
        graph = build_graph(checkpointer=MemorySaver())
        assert graph is not None

    def test_graph_compiles_without_checkpointer(self):
        from backend.app.graph.build_graph import build_graph
        graph = build_graph()
        assert graph is not None

    def test_all_required_nodes_registered(self):
        """Every node from the spec must be registered in the graph."""
        from backend.app.graph.build_graph import build_graph
        graph = build_graph()
        node_names = set(graph.nodes.keys())
        required = {
            "intake", "evidence", "prosecution", "defense",
            "fact_check", "evidence_quality", "cross_examination",
            "needs_human_input", "judge",
        }
        missing = required - node_names
        assert missing == set(), f"Graph is missing nodes: {missing}"


class TestGraphRunsEndToEnd:
    def test_invoke_on_fixture_case(self, minimal_state):
        """
        Graph must complete end-to-end on the fixture case
        with all mocks enabled and return a state with a verdict.
        """
        from langgraph.checkpoint.memory import MemorySaver
        from backend.app.graph.build_graph import build_graph

        graph = build_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": minimal_state["case_id"]}}

        result = graph.invoke(minimal_state, config=config)

        assert isinstance(result, dict)
        assert "verdict" in result
        assert result["verdict"] is not None

    def test_result_has_all_state_keys(self, minimal_state):
        from langgraph.checkpoint.memory import MemorySaver
        from backend.app.graph.build_graph import build_graph
        from backend.app.graph.state import CourtroomState

        graph = build_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": minimal_state["case_id"] + "-keys-test"}}
        result = graph.invoke(minimal_state, config=config)

        required_keys = set(CourtroomState.__annotations__.keys())
        missing = required_keys - set(result.keys())
        assert missing == set(), f"Result missing keys: {missing}"
