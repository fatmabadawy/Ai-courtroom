"""
tests/test_step1_scaffold.py
────────────────────────────
Step 1 — verify the repo scaffold is complete.
No external services required.
"""

import importlib
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
APP = PROJECT_ROOT / "backend" / "app"


class TestDirectoryStructure:
    """Assert every required directory exists."""

    def test_agents_dir(self):
        assert (APP / "agents").is_dir()

    def test_graph_dir(self):
        assert (APP / "graph").is_dir()

    def test_models_dir(self):
        assert (APP / "models").is_dir()

    def test_rag_dir(self):
        assert (APP / "rag").is_dir()

    def test_fixture_case_001(self):
        assert (PROJECT_ROOT / "tests" / "fixtures" / "case_001").is_dir()


class TestPackageMarkers:
    """Assert every package has an __init__.py."""

    PACKAGES = [
        "backend/app",
        "backend/app/agents",
        "backend/app/graph",
        "backend/app/models",
        "backend/app/rag",
        "tests",
        "tests/fixtures",
        "tests/fixtures/case_001",
    ]

    def test_all_init_files_exist(self):
        missing = [
            p
            for p in self.PACKAGES
            if not (PROJECT_ROOT / p / "__init__.py").exists()
        ]
        assert missing == [], f"Missing __init__.py in: {missing}"


class TestCoreModulesImport:
    """Assert config and llm_client import cleanly (no API keys needed)."""

    def test_config_imports(self):
        import backend.app.config as cfg  # noqa: F401

        # spot-check a few typed values
        assert isinstance(cfg.USE_MOCK_RAG, bool)
        assert isinstance(cfg.USE_MOCK_LLM, bool)
        assert isinstance(cfg.MAX_CROSS_EXAM_ROUNDS, int)

    def test_llm_client_imports(self):
        import backend.app.llm_client as llm  # noqa: F401

        assert callable(llm.get_llm_response)

    def test_llm_mock_returns_string(self, monkeypatch):
        """With USE_MOCK_LLM=true the shim must return the mock_response arg."""
        import backend.app.llm_client as llm

        monkeypatch.setattr(llm, "USE_MOCK_LLM", True)
        result = llm.get_llm_response("sys", "user", mock_response='{"ok": true}')
        assert result == '{"ok": true}'

    def test_pyproject_exists(self):
        assert (PROJECT_ROOT / "pyproject.toml").exists()

    def test_env_example_exists(self):
        assert (PROJECT_ROOT / ".env.example").exists()
