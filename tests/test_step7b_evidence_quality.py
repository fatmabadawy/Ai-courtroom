"""
tests/test_step7b_evidence_quality.py
──────────────────────────────────────
Step 7b — standalone unit tests for agents/evidence_quality.py.
Run against hand-built fixture evidence IDs without the graph.
"""

import pytest

from backend.app.agents.evidence_quality import (
    QUALITY_DISCLAIMER,
    METHODOLOGY_VERSION,
    W_RELIABILITY,
    W_DIRECTNESS,
    W_RELEVANCE,
    W_CORROBORATION,
    W_RECENCY,
    score_evidence,
)
from backend.app.models.schemas import EvidenceQualityScore


class TestWeights:
    def test_weights_sum_to_one(self):
        total = W_RELIABILITY + W_DIRECTNESS + W_RELEVANCE + W_CORROBORATION + W_RECENCY
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, not 1.0"

    def test_all_weights_positive(self):
        for name, w in [
            ("W_RELIABILITY", W_RELIABILITY),
            ("W_DIRECTNESS", W_DIRECTNESS),
            ("W_RELEVANCE", W_RELEVANCE),
            ("W_CORROBORATION", W_CORROBORATION),
            ("W_RECENCY", W_RECENCY),
        ]:
            assert w > 0, f"{name} must be positive"


class TestDisclaimer:
    def test_disclaimer_constant_non_empty(self):
        assert len(QUALITY_DISCLAIMER) > 0

    def test_disclaimer_mentions_heuristics(self):
        assert "heuristics" in QUALITY_DISCLAIMER.lower()

    def test_disclaimer_mentions_not_legal(self):
        assert "legal" in QUALITY_DISCLAIMER.lower()


class TestScoreEvidence:
    def test_returns_evidence_quality_score(self):
        score = score_evidence("EV-001")
        assert isinstance(score, EvidenceQualityScore)

    def test_all_five_dimensions_present(self):
        score = score_evidence("EV-001")
        for dim in ("reliability", "directness", "relevance", "corroboration", "recency"):
            assert hasattr(score, dim), f"Missing dimension: {dim}"
            assert 0.0 <= getattr(score, dim) <= 1.0, f"{dim} out of range"

    def test_composite_score_in_range(self):
        for eid in ("EV-001", "EV-002", "EV-003", "EV-MOCK-1", "EV-MOCK-3"):
            score = score_evidence(eid)
            assert 0.0 <= score.composite_score <= 1.0, (
                f"composite_score={score.composite_score} out of range for {eid}"
            )

    def test_methodology_version_set(self):
        score = score_evidence("EV-001")
        assert score.methodology_version == METHODOLOGY_VERSION

    def test_unknown_evidence_returns_valid_score(self):
        """Even for an unknown ID, the agent must return a valid score."""
        score = score_evidence("EV-NONEXISTENT-999")
        assert isinstance(score, EvidenceQualityScore)
        assert 0.0 <= score.composite_score <= 1.0

    def test_round_trip_serialisation(self):
        score = score_evidence("EV-002")
        reloaded = EvidenceQualityScore.model_validate_json(score.model_dump_json())
        assert reloaded.evidence_id == score.evidence_id
        assert abs(reloaded.composite_score - score.composite_score) < 1e-6

    def test_multiple_ids_all_scored(self):
        ids = ["EV-001", "EV-002", "EV-003"]
        scores = {eid: score_evidence(eid) for eid in ids}
        assert len(scores) == 3
        for eid, score in scores.items():
            assert score.evidence_id == eid


class TestCompositeFormula:
    def test_composite_matches_manual_calculation(self):
        """The composite score must equal the documented weighted formula."""
        score = score_evidence("EV-001")
        expected = (
            W_RELIABILITY * score.reliability
            + W_DIRECTNESS * score.directness
            + W_RELEVANCE * score.relevance
            + W_CORROBORATION * score.corroboration
            + W_RECENCY * score.recency
        )
        expected = max(0.0, min(1.0, expected))
        assert abs(score.composite_score - expected) < 1e-6, (
            f"composite_score={score.composite_score} doesn't match formula={expected}"
        )
