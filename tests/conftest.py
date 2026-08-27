"""
tests/conftest.py
─────────────────
Shared pytest fixtures available to all test modules.
"""

import json
import os
from pathlib import Path

import pytest

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
FIXTURE_CASE_001 = PROJECT_ROOT / "tests" / "fixtures" / "case_001"


# ── Environment: force mock mode for all tests ─────────────────────────────────
@pytest.fixture(autouse=True)
def force_mock_env(monkeypatch):
    """All tests run with mocks enabled — no API keys, no network."""
    monkeypatch.setenv("USE_MOCK_RAG", "true")
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    monkeypatch.setenv("USE_MOCK_GRAPH", "false")
    # Ensure the config module picks up the patched env
    import backend.app.config as cfg
    monkeypatch.setattr(cfg, "USE_MOCK_RAG", True)
    monkeypatch.setattr(cfg, "USE_MOCK_LLM", True)
    import backend.app.llm_client as llm
    monkeypatch.setattr(llm, "USE_MOCK_LLM", True)


# ── Fixture case ──────────────────────────────────────────────────────────────
@pytest.fixture
def case_001_metadata():
    """Load the fixture case metadata (expected_results.json)."""
    with open(FIXTURE_CASE_001 / "expected_results.json") as f:
        return json.load(f)


@pytest.fixture
def case_001_id(case_001_metadata):
    return case_001_metadata["case_id"]


@pytest.fixture
def case_001_expected(case_001_metadata):
    return case_001_metadata["expected_results"]


@pytest.fixture
def case_001_evidence_ids(case_001_metadata):
    return [e["evidence_id"] for e in case_001_metadata["evidence"]]


@pytest.fixture
def case_001_description(case_001_metadata):
    return case_001_metadata["description"]


# ── Minimal CourtroomState factory ─────────────────────────────────────────────
@pytest.fixture
def minimal_state(case_001_metadata):
    """
    Returns a CourtroomState-compatible dict pre-populated from case_001.
    All list fields are empty by default; individual tests add what they need.
    """
    from backend.app.models.schemas import JudgeProfile

    meta = case_001_metadata
    return {
        "case_id": meta["case_id"],
        "case_description": meta["description"],
        "parties": [],
        "claims": [],
        "legal_questions": meta["legal_questions"],
        "evidence_ids": [e["evidence_id"] for e in meta["evidence"]],
        "prosecution_arguments": [],
        "defense_arguments": [],
        "fact_checks": [],
        "evidence_quality": {},
        "cross_examinations": [],
        "unresolved_questions": [],
        "human_intervention": None,
        "judge_configuration": JudgeProfile(name="balanced"),
        "verdict": None,
        "round": 1,
    }
