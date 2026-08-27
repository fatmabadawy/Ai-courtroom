"""
backend/app/agents/judge.py
────────────────────────────
Judge Agent — Plan D.

Responsibilities:
  - Consumes the full CourtroomState.
  - Produces a Verdict per INTERFACES.md §3, including the disclaimer field.
  - Hard validation: every evidence_id in supporting_evidence_ids /
    opposing_evidence_ids must exist in state["evidence_ids"] — any
    hallucinated IDs are removed and flagged in unresolved_questions.
  - Supports three judge profiles (strict/balanced/skeptical) as
    prompt-level configuration only — same evidence, different lens.
"""

from __future__ import annotations

import json
import logging
from typing import List

from backend.app.graph.state import CourtroomState
from backend.app.llm_client import get_llm_response
from backend.app.models.schemas import JudgeProfile, Verdict

logger = logging.getLogger(__name__)

# ── Profile prompts ────────────────────────────────────────────────────────────

_PROFILE_INSTRUCTIONS = {
    "strict": (
        "You apply the law strictly and require clear, unambiguous evidence before "
        "finding in a party's favour. Ambiguous or circumstantial evidence is given "
        "minimal weight. When in doubt, you find for the defendant."
    ),
    "balanced": (
        "You weigh all evidence impartially, considering both the strength of "
        "supporting and contradicting evidence. You arrive at a verdict that "
        "reflects the overall balance of evidence."
    ),
    "skeptical": (
        "You apply heightened scrutiny to all evidence and arguments. You are "
        "particularly alert to gaps in the evidentiary chain, unsupported inferences, "
        "and potential bias. Your confidence scores tend to be lower."
    ),
}

_SYSTEM_PROMPT_TEMPLATE = """You are a senior judge presiding over a legal case.
Judge profile: {profile_name}
Profile instruction: {profile_instruction}

Your task is to review all arguments, fact-checks, and cross-examination results
and deliver a verdict.

Return a single JSON object:
{{
  "finding": str,                        // "For the plaintiff" | "For the defendant" | "Split"
  "supporting_evidence_ids": [str],      // IDs supporting your finding
  "opposing_evidence_ids": [str],        // IDs opposing your finding
  "unresolved_questions": [str],
  "reasoning": str,
  "confidence": float                    // 0.0–1.0
}}

IMPORTANT:
- Only cite evidence_ids from the provided list.
- confidence must be between 0.0 and 1.0.
- Return ONLY the JSON object — no markdown, no prose."""

_USER_PROMPT_TEMPLATE = """CASE: {case_id}

CLAIMS AND FACT-CHECKS:
{fact_check_block}

PROSECUTION ARGUMENTS:
{prosecution_block}

DEFENSE ARGUMENTS:
{defense_block}

CROSS-EXAMINATION OUTCOMES:
{cross_exam_block}

EVIDENCE QUALITY SUMMARY:
{quality_block}

Available evidence IDs: {evidence_ids}

Deliver your verdict."""


# ── Formatters ─────────────────────────────────────────────────────────────────

def _format_fact_checks(fact_checks: list) -> str:
    if not fact_checks:
        return "(none)"
    lines = []
    for fc in fact_checks:
        lines.append(
            f"  [{fc['claim_id']}] status={fc['status']} confidence={fc['confidence']:.2f}: "
            f"{fc['reasoning'][:100]}"
        )
    return "\n".join(lines)


def _format_arguments(arguments: list) -> str:
    if not arguments:
        return "(none)"
    lines = []
    for a in arguments:
        lines.append(
            f"  [{a['argument_id']}] claim={a['claim_id']} confidence={a['confidence']:.2f}: "
            f"{a['argument'][:120]}"
        )
    return "\n".join(lines)


def _format_cross_exams(rounds: list) -> str:
    if not rounds:
        return "(none)"
    lines = []
    for r in rounds:
        lines.append(
            f"  Round {r['round']}: target={r['target_argument_id']} "
            f"outcome={r['outcome']}"
        )
    return "\n".join(lines)


def _format_quality(quality: dict) -> str:
    if not quality:
        return "(none)"
    lines = []
    for eid, score in list(quality.items())[:5]:  # top 5 for brevity
        lines.append(
            f"  [{eid}] composite={score['composite_score']:.3f}"
        )
    return "\n".join(lines)


# ── Mock verdict ───────────────────────────────────────────────────────────────

def _mock_verdict(profile: str, evidence_ids: List[str]) -> str:
    if profile == "strict":
        return json.dumps({
            "finding": "For the defendant",
            "supporting_evidence_ids": [evidence_ids[1], evidence_ids[2]] if len(evidence_ids) >= 3 else evidence_ids,
            "opposing_evidence_ids": [evidence_ids[0]] if evidence_ids else [],
            "unresolved_questions": ["Exact damages calculation remains unresolved"],
            "reasoning": (
                "[STRICT] The force majeure clause (§9.3) has been established by "
                "expert testimony. In the absence of clear evidence of breach, "
                "I find for the defendant."
            ),
            "confidence": 0.72,
        })
    elif profile == "skeptical":
        return json.dumps({
            "finding": "Split",
            "supporting_evidence_ids": evidence_ids[:1] if evidence_ids else [],
            "opposing_evidence_ids": evidence_ids[1:2] if len(evidence_ids) > 1 else [],
            "unresolved_questions": [
                "Force majeure certification process not fully documented",
                "Alternative supplier search not independently verified",
            ],
            "reasoning": (
                "[SKEPTICAL] While some evidence supports force majeure, "
                "significant gaps remain in the evidentiary record. "
                "I find partially for each party."
            ),
            "confidence": 0.51,
        })
    else:  # balanced
        return json.dumps({
            "finding": "For the defendant",
            "supporting_evidence_ids": evidence_ids[1:] if len(evidence_ids) > 1 else evidence_ids,
            "opposing_evidence_ids": [],
            "unresolved_questions": ["Damages quantum remains to be determined"],
            "reasoning": (
                "[BALANCED] The balance of evidence supports the force majeure defence. "
                "The contract clause, internal communications, and expert testimony "
                "collectively establish the qualifying event."
            ),
            "confidence": 0.81,
        })


# ── Hard validation ────────────────────────────────────────────────────────────

def _validate_evidence_ids(
    cited_ids: List[str],
    valid_ids: set,
    field_name: str,
    verdict_unresolved: List[str],
) -> List[str]:
    """
    Remove any evidence_id not in valid_ids.
    Append a flag to verdict_unresolved for each hallucinated ID.
    Returns the cleaned list.
    """
    clean = []
    for eid in cited_ids:
        if eid in valid_ids:
            clean.append(eid)
        else:
            msg = (
                f"Judge hallucination: {field_name} cited evidence_id={eid!r} "
                "which does not exist in state['evidence_ids'] — removed."
            )
            logger.warning(msg)
            verdict_unresolved.append(msg)
    return clean


# ── Core logic ─────────────────────────────────────────────────────────────────

def deliberate(state: CourtroomState, profile_name: str = "balanced") -> Verdict:
    """
    Pure function: produce a Verdict from the full CourtroomState.
    Testable standalone without the graph.
    """
    valid_ids = set(state.get("evidence_ids", []))

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        profile_name=profile_name,
        profile_instruction=_PROFILE_INSTRUCTIONS.get(profile_name, _PROFILE_INSTRUCTIONS["balanced"]),
    )

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        case_id=state["case_id"],
        fact_check_block=_format_fact_checks(state.get("fact_checks", [])),
        prosecution_block=_format_arguments(state.get("prosecution_arguments", [])),
        defense_block=_format_arguments(state.get("defense_arguments", [])),
        cross_exam_block=_format_cross_exams(state.get("cross_examinations", [])),
        quality_block=_format_quality(state.get("evidence_quality", {})),
        evidence_ids=", ".join(sorted(valid_ids)) if valid_ids else "(none)",
    )

    mock_resp = _mock_verdict(profile_name, sorted(valid_ids))

    raw = get_llm_response(system_prompt, user_prompt, mock_response=mock_resp)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Judge JSON parse error: %s — returning empty verdict.", exc)
        data = {
            "finding": "Undetermined",
            "supporting_evidence_ids": [],
            "opposing_evidence_ids": [],
            "unresolved_questions": [f"Judge parse error: {exc}"],
            "reasoning": "Verdict could not be produced due to a parse error.",
            "confidence": 0.0,
        }

    # Hard validation: strip hallucinated evidence_ids
    unresolved = list(data.get("unresolved_questions", []))
    supporting = _validate_evidence_ids(
        data.get("supporting_evidence_ids", []), valid_ids, "supporting_evidence_ids", unresolved
    )
    opposing = _validate_evidence_ids(
        data.get("opposing_evidence_ids", []), valid_ids, "opposing_evidence_ids", unresolved
    )

    verdict = Verdict(
        finding=data.get("finding", "Undetermined"),
        supporting_evidence_ids=supporting,
        opposing_evidence_ids=opposing,
        unresolved_questions=unresolved,
        reasoning=data.get("reasoning", ""),
        confidence=max(0.0, min(1.0, float(data.get("confidence", 0.0)))),
        judge_profile=profile_name,
        # disclaimer is set by Verdict schema default
    )

    logger.info(
        "Verdict [%s]: finding=%r confidence=%.2f",
        profile_name, verdict.finding, verdict.confidence,
    )
    return verdict


def node(state: CourtroomState) -> CourtroomState:
    """
    Judge node: runs deliberation and populates state["verdict"].
    Uses judge_configuration from state.
    """
    profile_raw = state.get("judge_configuration")
    if isinstance(profile_raw, dict):
        profile = JudgeProfile.model_validate(profile_raw)
    elif isinstance(profile_raw, JudgeProfile):
        profile = profile_raw
    else:
        profile = JudgeProfile(name="balanced")

    verdict = deliberate(state, profile.name)

    return {
        **state,
        "verdict": verdict.model_dump(),
        "unresolved_questions": list(state.get("unresolved_questions", []))
        + verdict.unresolved_questions,
    }
