"""
backend/app/agents/cross_examiner.py
──────────────────────────────────────
Cross-Examination Agent — Plan D.

Implements a bounded sub-loop per PLAN_D §"Cross-Examination":
  select weakest/contested argument
  → generate challenge question
  → route to responding side (which generates a response)
  → Fact Checker re-evaluates the affected claim
  → record outcome in CrossExaminationRound
  → round += 1

Hard termination (any ONE of):
  1. round >= MAX_ROUNDS (from config)
  2. confidence delta below CONVERGENCE_THRESHOLD for all contested args
  3. No contested arguments remain

Immutability rule (PLAN_D):
  Prior CrossExaminationRound objects are NEVER mutated or deleted.
  New rounds are appended.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from backend.app.agents.fact_checker import check_claim
from backend.app.config import (
    CROSS_EXAM_CONVERGENCE_THRESHOLD,
    MAX_CROSS_EXAM_ROUNDS,
)
from backend.app.graph.state import CourtroomState
from backend.app.llm_client import get_llm_response
from backend.app.models.schemas import (
    Argument,
    Claim,
    CrossExaminationRound,
    FactCheck,
)

logger = logging.getLogger(__name__)

# ── Prompts ────────────────────────────────────────────────────────────────────

_CHALLENGE_SYSTEM = """You are a rigorous cross-examiner in a legal proceeding.
Given a weakly-supported argument, generate a single, focused challenge question
that probes the weakest link in the argument's evidence or reasoning.

Return a JSON object:
{
  "question": str   // the challenge question (one sentence)
}

Return ONLY the JSON object."""

_RESPONSE_SYSTEM = """You are a legal advocate responding to a cross-examination challenge.
Given the original argument and a challenge question, provide a concise response
that either strengthens, maintains, or concedes weakness in the argument.

Return a JSON object:
{
  "response": str,                              // your response
  "outcome": "strengthened" | "weakened" | "unchanged"
}

Return ONLY the JSON object."""

_CHALLENGE_PROMPT = """Argument (argument_id={argument_id}, side={side}):
"{argument_text}"

Evidence cited: {evidence_ids}

Generate a challenge question targeting the weakest point."""

_RESPONSE_PROMPT = """Argument (argument_id={argument_id}):
"{argument_text}"

Challenge question: "{question}"

Respond to the challenge."""


# ── Mock helpers ───────────────────────────────────────────────────────────────

def _mock_challenge(arg: Argument) -> str:
    return json.dumps({
        "question": (
            f"Can you provide independent corroboration for your claim that "
            f"'{arg.argument[:60]}...' beyond the evidence already cited?"
        )
    })


def _mock_response(arg: Argument, question: str, round_num: int) -> str:
    # Alternate outcomes to keep tests interesting
    outcomes = ["weakened", "unchanged", "strengthened"]
    outcome = outcomes[round_num % len(outcomes)]
    return json.dumps({
        "response": f"[Round {round_num}] The evidence stands as presented.",
        "outcome": outcome,
    })


# ── Selection logic ────────────────────────────────────────────────────────────

def _is_contested(arg: Argument) -> bool:
    """
    An argument is contested if it has evidence but low confidence,
    or if it rebutted by an opposing argument.
    """
    return arg.confidence < 0.6 and bool(arg.evidence_ids)


def _select_weakest(arguments: List[Argument]) -> Optional[Argument]:
    """
    Select the weakest contested argument by lowest confidence.
    Returns None if no contested arguments exist.
    """
    contested = [a for a in arguments if _is_contested(a)]
    if not contested:
        return None
    return min(contested, key=lambda a: a.confidence)


def _all_arguments(state: CourtroomState) -> List[Argument]:
    all_args = []
    for raw in state.get("prosecution_arguments", []):
        a = Argument.model_validate(raw) if isinstance(raw, dict) else raw
        all_args.append(a)
    for raw in state.get("defense_arguments", []):
        a = Argument.model_validate(raw) if isinstance(raw, dict) else raw
        all_args.append(a)
    return all_args


def _get_claim(state: CourtroomState, claim_id: str) -> Optional[Claim]:
    for raw in state.get("claims", []):
        c = Claim.model_validate(raw) if isinstance(raw, dict) else raw
        if c.claim_id == claim_id:
            return c
    return None


# ── Core loop ─────────────────────────────────────────────────────────────────

def run_cross_examination(
    state: CourtroomState,
    max_rounds: int = MAX_CROSS_EXAM_ROUNDS,
    convergence_threshold: float = CROSS_EXAM_CONVERGENCE_THRESHOLD,
) -> List[CrossExaminationRound]:
    """
    Pure function: run the cross-examination loop.
    Returns the list of CrossExaminationRound objects produced.
    Does NOT modify state — the node wraps this and updates state.
    Testable standalone without the full graph.
    """
    # Deserialise existing rounds (state stores them as dicts after serialisation)
    raw_rounds = state.get("cross_examinations", [])
    rounds: List[CrossExaminationRound] = [
        CrossExaminationRound.model_validate(r) if isinstance(r, dict) else r
        for r in raw_rounds
    ]
    case_id = state["case_id"]
    round_num = len(rounds) + 1

    # Confidence tracking for convergence detection
    prev_confidences: dict[str, float] = {}
    for arg in _all_arguments(state):
        prev_confidences[arg.argument_id] = arg.confidence

    # Working copy of arguments (we track confidence updates locally)
    working_confidences = dict(prev_confidences)

    while round_num <= max_rounds:
        # Termination: no contested arguments
        contested = [a for a in _all_arguments(state) if _is_contested(a)]
        if not contested:
            logger.info(
                "Cross-examination: no contested arguments at round %d — stopping.",
                round_num,
            )
            break

        target_arg = _select_weakest(_all_arguments(state))
        if target_arg is None:
            break

        logger.info(
            "Cross-examination round %d: targeting argument=%r (confidence=%.2f)",
            round_num, target_arg.argument_id, target_arg.confidence,
        )

        # Generate challenge
        challenge_user = _CHALLENGE_PROMPT.format(
            argument_id=target_arg.argument_id,
            side=target_arg.side,
            argument_text=target_arg.argument,
            evidence_ids=target_arg.evidence_ids,
        )
        raw_challenge = get_llm_response(
            _CHALLENGE_SYSTEM,
            challenge_user,
            mock_response=_mock_challenge(target_arg),
        )
        try:
            question = json.loads(raw_challenge)["question"]
        except Exception:
            question = "Can you elaborate on the evidence supporting this argument?"

        # Generate response from the targeted side
        response_user = _RESPONSE_PROMPT.format(
            argument_id=target_arg.argument_id,
            argument_text=target_arg.argument,
            question=question,
        )
        raw_response = get_llm_response(
            _RESPONSE_SYSTEM,
            response_user,
            mock_response=_mock_response(target_arg, question, round_num),
        )
        try:
            resp_data = json.loads(raw_response)
            response_text = resp_data.get("response", "")
            raw_outcome = resp_data.get("outcome", "unchanged")
            if raw_outcome not in ("strengthened", "weakened", "unchanged"):
                raw_outcome = "unchanged"
            outcome = raw_outcome
        except Exception:
            response_text = ""
            outcome = "unchanged"

        # Fact Checker re-evaluates the claim
        claim = _get_claim(state, target_arg.claim_id)
        if claim:
            fc = check_claim(claim, case_id)
            logger.info(
                "Cross-exam re-check: claim=%r → status=%s confidence=%.2f",
                claim.claim_id, fc.status, fc.confidence,
            )
            # Update working confidence
            working_confidences[target_arg.argument_id] = fc.confidence

        # Record round (never mutate prior rounds)
        new_round = CrossExaminationRound(
            round=round_num,
            challenger="cross_examiner",
            target_argument_id=target_arg.argument_id,
            question=question,
            response=response_text,
            outcome=outcome,
        )
        rounds.append(new_round)

        # Convergence check: if confidence delta is below threshold for all args
        deltas = [
            abs(working_confidences.get(aid, 0) - prev_confidences.get(aid, 0))
            for aid in working_confidences
        ]
        if all(d < convergence_threshold for d in deltas):
            logger.info(
                "Cross-examination: convergence at round %d (max delta=%.4f) — stopping.",
                round_num, max(deltas) if deltas else 0,
            )
            # Only stop after at least one round has run
            if round_num >= 1:
                round_num += 1
                break

        prev_confidences = dict(working_confidences)
        round_num += 1

    return rounds


def node(state: CourtroomState) -> CourtroomState:
    """
    Cross-Examination node: runs the bounded loop and appends new rounds.
    Existing cross_examinations are preserved (immutability rule).
    """
    new_rounds = run_cross_examination(state)
    updated_round = state.get("round", 1) + len(new_rounds)

    return {
        **state,
        "cross_examinations": [r.model_dump() for r in new_rounds],
        "round": updated_round,
    }
