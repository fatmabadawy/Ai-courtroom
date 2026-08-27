"""
backend/app/agents/_argument_builder.py
────────────────────────────────────────
Shared argument-building logic for Prosecution and Defense agents (Plan C).

Parameterized by `side: Literal["prosecution", "defense"]`.
Both agents import and call `build_arguments()` — no code duplication.

Enforcement (PLAN_C, in-code not just prompt):
  - confidence > 0.3 → must have non-empty evidence_ids.
    If LLM returns confidence > 0.3 with no evidence, confidence is clamped
    to 0.3 and a warning is logged.

argument_id generation (DEVIATION #5):
  f"{side}-{claim_id}-r{round}"
"""

from __future__ import annotations

import json
import logging
from typing import List, Literal, Optional

from backend.app.llm_client import get_llm_response
from backend.app.models.schemas import Argument, Claim
from backend.app.rag.retrieve import retrieve

logger = logging.getLogger(__name__)

Side = Literal["prosecution", "defense"]

# ── Prompts ────────────────────────────────────────────────────────────────────

_SYSTEM_PROSECUTION = """You are the prosecution attorney in a legal case.
Your task is to build the strongest evidence-based argument supporting the
prosecution's position on the given claim.

Return a JSON object:
{
  "argument": str,          // your argument text
  "evidence_ids": [str],    // IDs of evidence that support this argument
  "source_ids": [str],      // optional source document IDs
  "confidence": float,      // 0.0–1.0; must be <= 0.3 if evidence_ids is empty
  "responds_to_argument_id": null  // prosecution never rebuts
}

Rules:
- Only cite evidence_ids from the provided list.
- If you have no evidence, set confidence <= 0.3 and evidence_ids to [].
- Return ONLY the JSON object."""

_SYSTEM_DEFENSE = """You are the defense attorney in a legal case.
Your task is to build the strongest evidence-based counter-argument on the
given claim, rebutting the prosecution's position where possible.

Return a JSON object:
{
  "argument": str,
  "evidence_ids": [str],
  "source_ids": [str],
  "confidence": float,
  "responds_to_argument_id": str | null  // set to prosecution argument_id if rebutting
}

Rules:
- Only cite evidence_ids from the provided list.
- If you have no evidence, set confidence <= 0.3 and evidence_ids to [].
- Set responds_to_argument_id to the prosecution argument_id you are directly rebutting.
- Return ONLY the JSON object."""

_USER_PROMPT_TEMPLATE = """Case claim (claim_id={claim_id}):
"{statement}"

Available evidence:
{evidence_blocks}

{prior_block}

Build your argument."""


def _format_evidence_blocks(evidence) -> str:
    if not evidence:
        return "(no evidence retrieved)"
    return "\n".join(
        f"[{e.evidence_id}] (relevance={e.relevance_score:.2f}): {e.content}"
        for e in evidence
    )


def _format_prior_block(side: Side, prior_arguments: Optional[List]) -> str:
    if side == "prosecution" or not prior_arguments:
        return ""
    lines = ["Prosecution arguments to rebut:"]
    for a in prior_arguments:
        arg = Argument.model_validate(a) if isinstance(a, dict) else a
        lines.append(
            f"  [{arg.argument_id}] claim={arg.claim_id}: {arg.argument[:120]}..."
        )
    return "\n".join(lines)


def _mock_argument(
    side: Side,
    claim: Claim,
    evidence,
    prior_arguments: Optional[List],
    round_num: int,
) -> str:
    ev_ids = [e.evidence_id for e in evidence]
    stmt_lower = claim.statement.lower()

    if side == "prosecution":
        if "force majeure" in stmt_lower or "excused" in stmt_lower:
            # Prosecution opposes force majeure
            return json.dumps({
                "argument": (
                    "The defendant has failed to prove that a qualifying force majeure "
                    "event occurred. The export control notice has not been independently "
                    "verified and alternative suppliers were available."
                ),
                "evidence_ids": [],
                "source_ids": [],
                "confidence": 0.25,
                "responds_to_argument_id": None,
            })
        # Prosecution supports payment claim
        return json.dumps({
            "argument": (
                "The contract (§4.2) required delivery by March 31, 2024. "
                "WidgetCo failed to deliver and no valid excuse was provided."
            ),
            "evidence_ids": ev_ids[:1] if ev_ids else [],
            "source_ids": [],
            "confidence": 0.65,
            "responds_to_argument_id": None,
        })
    else:
        # Defense
        responds_to = None
        if prior_arguments:
            matching = [
                a for a in prior_arguments
                if (a["claim_id"] if isinstance(a, dict) else a.claim_id) == claim.claim_id
            ]
            if matching:
                a0 = matching[0]
                responds_to = a0["argument_id"] if isinstance(a0, dict) else a0.argument_id

        if "force majeure" in stmt_lower or "excused" in stmt_lower:
            return json.dumps({
                "argument": (
                    "Section 9.3 of the contract explicitly covers government export controls. "
                    "The expert witness confirmed the Fab-Taiwan notice is authentic and no "
                    "commercially reasonable alternative was available."
                ),
                "evidence_ids": ev_ids,
                "source_ids": [],
                "confidence": 0.85,
                "responds_to_argument_id": responds_to,
            })
        # Defense on payment claim
        return json.dumps({
            "argument": (
                "ACME Corp's own records show a prepayment of $125,000 was received "
                "by WidgetCo on January 20, 2024 — prior to the alleged breach date."
            ),
            "evidence_ids": [e.evidence_id for e in evidence if "payment" in e.content.lower()]
                           or ev_ids[:1],
            "source_ids": [],
            "confidence": 0.80,
            "responds_to_argument_id": responds_to,
        })


def _enforce_confidence_rule(arg: Argument) -> Argument:
    """
    PLAN_C enforcement: confidence > 0.3 requires non-empty evidence_ids.
    If violated, clamp confidence to 0.3 and log a warning.
    """
    if arg.confidence > 0.3 and not arg.evidence_ids:
        logger.warning(
            "Argument %r has confidence=%.2f but empty evidence_ids — "
            "clamping confidence to 0.3 (PLAN_C enforcement).",
            arg.argument_id, arg.confidence,
        )
        return arg.model_copy(update={"confidence": 0.3})
    return arg


def build_arguments(
    state: dict,
    side: Side,
    prior_arguments: Optional[List],
    round_num: int = 1,
) -> List[Argument]:
    """
    Core shared logic: retrieve evidence per claim, call LLM, return Arguments.
    """
    case_id = state["case_id"]
    claims_raw = state.get("claims", [])
    valid_evidence_ids = set(state.get("evidence_ids", []))
    system_prompt = _SYSTEM_PROSECUTION if side == "prosecution" else _SYSTEM_DEFENSE

    arguments: List[Argument] = []

    for claim_data in claims_raw:
        claim = Claim.model_validate(claim_data) if isinstance(claim_data, dict) else claim_data

        # Per-claim RAG retrieval (PLAN_C: each agent issues its own queries)
        evidence = retrieve(case_id, claim.statement)

        mock_resp = _mock_argument(side, claim, evidence, prior_arguments, round_num)
        prior_block = _format_prior_block(side, prior_arguments)

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            claim_id=claim.claim_id,
            statement=claim.statement,
            evidence_blocks=_format_evidence_blocks(evidence),
            prior_block=prior_block,
        )

        raw = get_llm_response(system_prompt, user_prompt, mock_response=mock_resp)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(
                "Argument parse error for %s claim=%r: %s — skipping.",
                side, claim.claim_id, exc,
            )
            # Emit "no evidence found" argument rather than crashing
            data = {
                "argument": f"[Parse error — no argument could be constructed for {claim.claim_id}]",
                "evidence_ids": [],
                "source_ids": [],
                "confidence": 0.0,
                "responds_to_argument_id": None,
            }

        # Strip hallucinated evidence IDs
        raw_ev_ids = data.get("evidence_ids", [])
        clean_ev_ids = [eid for eid in raw_ev_ids if eid in valid_evidence_ids]
        if len(clean_ev_ids) < len(raw_ev_ids):
            stripped = set(raw_ev_ids) - set(clean_ev_ids)
            logger.warning(
                "%s argument for claim=%r stripped hallucinated evidence_ids: %s",
                side, claim.claim_id, stripped,
            )

        argument_id = f"{side}-{claim.claim_id}-r{round_num}"

        arg = Argument(
            argument_id=argument_id,
            claim_id=claim.claim_id,
            argument=data.get("argument", ""),
            evidence_ids=clean_ev_ids,
            source_ids=data.get("source_ids", []),
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.0)))),
            side=side,
            round=round_num,
            responds_to_argument_id=data.get("responds_to_argument_id"),
        )

        # Enforce PLAN_C rule
        arg = _enforce_confidence_rule(arg)
        arguments.append(arg)
        logger.info(
            "%s argument for claim=%r: confidence=%.2f evidence_ids=%s",
            side, claim.claim_id, arg.confidence, arg.evidence_ids,
        )

    return arguments
