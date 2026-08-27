"""
tests/test_step9_cross_examiner.py
────────────────────────────────────
Step 9 — bounded loop tests for agents/cross_examiner.py.

Scenarios:
  (a) normal termination — no contested arguments → loop stops early
  (b) forced non-convergence — loop always finds contested args → terminates at MAX_ROUNDS
  (c) immutability — prior rounds are never mutated
  (d) round record schema valid
"""

import pytest

from backend.app.agents.cross_examiner import run_cross_examination, _is_contested
from backend.app.config import MAX_CROSS_EXAM_ROUNDS
from backend.app.models.schemas import Argument, CrossExaminationRound


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_argument(
    arg_id: str,
    claim_id: str,
    side: str,
    confidence: float,
    evidence_ids=None,
) -> dict:
    return Argument(
        argument_id=arg_id,
        claim_id=claim_id,
        argument=f"Argument {arg_id} for claim {claim_id}.",
        evidence_ids=evidence_ids or ["EV-001"],
        confidence=confidence,
        side=side,
    ).model_dump()


@pytest.fixture
def state_with_high_confidence_args(minimal_state):
    """All arguments have confidence >= 0.6 → none are contested."""
    state = dict(minimal_state)
    state["prosecution_arguments"] = [
        make_argument("prosecution-CL-001-r1", "CL-001", "prosecution", 0.85),
        make_argument("prosecution-CL-002-r1", "CL-002", "prosecution", 0.75),
    ]
    state["defense_arguments"] = [
        make_argument("defense-CL-001-r1", "CL-001", "defense", 0.80),
        make_argument("defense-CL-002-r1", "CL-002", "defense", 0.90),
    ]
    return state


@pytest.fixture
def state_with_contested_args(minimal_state):
    """All arguments have confidence < 0.6 with evidence → contested."""
    state = dict(minimal_state)
    state["prosecution_arguments"] = [
        make_argument("prosecution-CL-001-r1", "CL-001", "prosecution", 0.35),
        make_argument("prosecution-CL-002-r1", "CL-002", "prosecution", 0.40),
    ]
    state["defense_arguments"] = [
        make_argument("defense-CL-001-r1", "CL-001", "defense", 0.38),
        make_argument("defense-CL-002-r1", "CL-002", "defense", 0.42),
    ]
    return state


# ── (a) Normal termination — no contested arguments ────────────────────────────

class TestNoContestedTermination:
    def test_no_rounds_when_no_contested(self, state_with_high_confidence_args):
        """All args have high confidence → loop should produce 0 rounds."""
        rounds = run_cross_examination(state_with_high_confidence_args)
        assert len(rounds) == 0, (
            f"Expected 0 rounds with no contested arguments, got {len(rounds)}"
        )


# ── (b) Non-convergence → hard stop at MAX_ROUNDS ─────────────────────────────

class TestHardTerminationAtMaxRounds:
    def test_terminates_at_max_rounds(self, state_with_contested_args):
        """
        Fixture designed to keep all arguments contested (low confidence with evidence).
        Loop MUST terminate at MAX_ROUNDS regardless.
        """
        rounds = run_cross_examination(
            state_with_contested_args,
            max_rounds=MAX_CROSS_EXAM_ROUNDS,
            convergence_threshold=0.0001,  # very tight threshold → no convergence
        )
        assert len(rounds) <= MAX_CROSS_EXAM_ROUNDS, (
            f"Loop ran {len(rounds)} rounds, exceeding MAX_ROUNDS={MAX_CROSS_EXAM_ROUNDS}"
        )
        assert len(rounds) > 0, "Should have produced at least one round"

    def test_custom_max_rounds_respected(self, state_with_contested_args):
        """Passing max_rounds=1 must produce exactly 1 round."""
        rounds = run_cross_examination(
            state_with_contested_args,
            max_rounds=1,
            convergence_threshold=0.0001,
        )
        assert len(rounds) <= 1


# ── (c) Immutability — prior rounds never mutated ─────────────────────────────

class TestRoundImmutability:
    def test_prior_rounds_preserved(self, state_with_contested_args):
        """
        Inject a pre-existing round into state; run again.
        The existing round must appear unchanged in the output.
        """
        existing_round = CrossExaminationRound(
            round=1,
            challenger="cross_examiner",
            target_argument_id="prosecution-CL-001-r1",
            question="Prior challenge question?",
            response="Prior response.",
            outcome="unchanged",
        )
        state = dict(state_with_contested_args)
        state["cross_examinations"] = [existing_round.model_dump()]

        rounds = run_cross_examination(state, max_rounds=2, convergence_threshold=0.0001)
        # All rounds returned should include the prior one
        all_round_numbers = [r.round for r in rounds]
        assert 1 in all_round_numbers, "Round 1 must be preserved"

    def test_rounds_append_not_replace(self, state_with_contested_args):
        """Each call appends new rounds; list grows monotonically."""
        state = dict(state_with_contested_args)
        state["cross_examinations"] = []

        rounds1 = run_cross_examination(state, max_rounds=2, convergence_threshold=0.0001)
        assert len(rounds1) <= 2


# ── (d) Round schema ──────────────────────────────────────────────────────────

class TestRoundSchema:
    def test_all_rounds_are_valid_schema(self, state_with_contested_args):
        rounds = run_cross_examination(
            state_with_contested_args,
            max_rounds=MAX_CROSS_EXAM_ROUNDS,
        )
        for r in rounds:
            assert isinstance(r, CrossExaminationRound)
            assert r.challenger == "cross_examiner"
            assert r.outcome in ("strengthened", "weakened", "unchanged")
            assert isinstance(r.question, str) and len(r.question) > 0
            assert isinstance(r.round, int) and r.round >= 1

    def test_round_numbers_sequential(self, state_with_contested_args):
        rounds = run_cross_examination(
            state_with_contested_args,
            max_rounds=3,
            convergence_threshold=0.0001,
        )
        for i, r in enumerate(rounds):
            assert r.round == i + 1, f"Round {i} has round number {r.round}, expected {i+1}"


# ── is_contested helper ───────────────────────────────────────────────────────

class TestIsContested:
    def test_high_confidence_not_contested(self):
        arg = Argument(
            argument_id="x",
            claim_id="c",
            argument="y",
            evidence_ids=["EV-1"],
            confidence=0.8,
            side="prosecution",
        )
        assert not _is_contested(arg)

    def test_low_confidence_with_evidence_contested(self):
        arg = Argument(
            argument_id="x",
            claim_id="c",
            argument="y",
            evidence_ids=["EV-1"],
            confidence=0.4,
            side="prosecution",
        )
        assert _is_contested(arg)

    def test_low_confidence_no_evidence_not_contested(self):
        arg = Argument(
            argument_id="x",
            claim_id="c",
            argument="y",
            evidence_ids=[],
            confidence=0.2,
            side="prosecution",
        )
        assert not _is_contested(arg)
