"""
backend/app/agents/fact_checker.py
────────────────────────────────────
Fact Checker Agent — Plan D.

Responsibilities:
  - For each Claim in state, runs INDEPENDENT retrieval (never reuses the
    evidence_ids already cited by Prosecution/Defense).
  - Produces a FactCheck per claim with status:
      SUPPORTED | CONTRADICTED | PARTIALLY_SUPPORTED | UNVERIFIED
    (exactly the Literal values in INTERFACES.md §3).
  - Populates state["fact_checks"].

Design note: The agent is a pure function of
  (claims, evidence) and is testable without the graph.
"""

from __future__ import annotations

import json
import logging
from typing import List

from backend.app.graph.state import CourtroomState
from backend.app.llm_client import get_llm_response
from backend.app.models.schemas import Claim, EvidenceResult, FactCheck
from backend.app.rag.retrieve import retrieve

logger = logging.getLogger(__name__)

# ── Status literal (mirrors INTERFACES.md §3 exactly) ─────────────────────────
VALID_STATUSES = frozenset({"SUPPORTED", "CONTRADICTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"})

# ── Prompt ─────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an objective legal fact-checker.
Given a claim and a set of retrieved evidence, determine whether the evidence
supports, contradicts, partially supports, or does not address the claim.

Return a single JSON object with these fields:
{
  "claim_id": str,
  "status": "SUPPORTED" | "CONTRADICTED" | "PARTIALLY_SUPPORTED" | "UNVERIFIED",
  "supporting_evidence_ids": [str],   // evidence IDs that support the claim
  "contradicting_evidence_ids": [str], // evidence IDs that contradict the claim
  "confidence": float,                // 0.0–1.0
  "reasoning": str                    // brief explanation
}

Rules:
- Only reference evidence_ids from the provided list.
- status must be EXACTLY one of the four values above (case-sensitive).
- confidence must be between 0.0 and 1.0.
- Return ONLY the JSON object — no prose, no markdown."""

_USER_PROMPT_TEMPLATE = """Claim (claim_id={claim_id}):
"{statement}"

Retrieved evidence (do NOT reuse Prosecution/Defense citations — evaluate independently):
{evidence_blocks}

Return the FactCheck JSON."""


def _format_evidence_blocks(evidence: List[EvidenceResult]) -> str:
    lines = []
    for e in evidence:
        lines.append(f"[{e.evidence_id}] (relevance={e.relevance_score:.2f}): {e.content}")
    return "\n".join(lines) if lines else "(no evidence retrieved)"


def _mock_fact_check(claim: Claim, evidence: List[EvidenceResult]) -> str:
    """
    Deterministic mock fact-check output.
    Uses keyword heuristics for testing:
      - Claims mentioning "NO payment" + contradicting evidence → CONTRADICTED
      - Claims mentioning "force majeure" + supporting evidence → SUPPORTED
      - Otherwise → UNVERIFIED
    """
    stmt_lower = claim.statement.lower()
    ev_ids = [e.evidence_id for e in evidence]

    if "no payment" in stmt_lower or "made no payment" in stmt_lower:
        # CL-001 type: contradicted by payment records
        contra_ids = [e.evidence_id for e in evidence if "payment" in e.content.lower()]
        return json.dumps({
            "claim_id": claim.claim_id,
            "status": "CONTRADICTED",
            "supporting_evidence_ids": [],
            "contradicting_evidence_ids": contra_ids or ev_ids[:1],
            "confidence": 0.88,
            "reasoning": (
                "Evidence records show a prepayment was made prior to the alleged "
                "breach date, directly contradicting the claim."
            ),
        })

    if "force majeure" in stmt_lower or "excused" in stmt_lower:
        # CL-002 type: supported by contract + witness statement
        return json.dumps({
            "claim_id": claim.claim_id,
            "status": "SUPPORTED",
            "supporting_evidence_ids": ev_ids,
            "contradicting_evidence_ids": [],
            "confidence": 0.85,
            "reasoning": (
                "Contract clause §9.3 permits force majeure; witness confirms the "
                "government export control qualifies; no commercially reasonable "
                "alternative was available."
            ),
        })

    return json.dumps({
        "claim_id": claim.claim_id,
        "status": "UNVERIFIED",
        "supporting_evidence_ids": [],
        "contradicting_evidence_ids": [],
        "confidence": 0.3,
        "reasoning": "Insufficient evidence to make a determination.",
    })


def _parse_fact_check(raw: str, claim_id: str) -> FactCheck:
    data = json.loads(raw)
    # Normalise status — guard against LLM case variations
    data["status"] = data.get("status", "UNVERIFIED").upper()
    if data["status"] not in VALID_STATUSES:
        logger.warning(
            "Fact checker returned unknown status=%r for claim=%r — defaulting to UNVERIFIED",
            data["status"], claim_id,
        )
        data["status"] = "UNVERIFIED"
    # Clamp confidence
    data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    return FactCheck.model_validate(data)


def check_claim(
    claim: Claim,
    case_id: str,
) -> FactCheck:
    """
    Pure function: fact-check a single claim.
    Performs its own independent retrieval (PLAN_D requirement).
    Testable standalone without the full graph.
    """
    # Independent retrieval — fresh query, not reusing Prosecution/Defense IDs.
    evidence = retrieve(case_id, claim.statement)

    mock_resp = _mock_fact_check(claim, evidence)
    user_prompt = _USER_PROMPT_TEMPLATE.format(
        claim_id=claim.claim_id,
        statement=claim.statement,
        evidence_blocks=_format_evidence_blocks(evidence),
    )

    raw = get_llm_response(
        _SYSTEM_PROMPT,
        user_prompt,
        mock_response=mock_resp,
    )

    try:
        return _parse_fact_check(raw, claim.claim_id)
    except Exception as exc:
        logger.error(
            "Fact checker parse error for claim=%r: %s — returning UNVERIFIED",
            claim.claim_id, exc,
        )
        return FactCheck(
            claim_id=claim.claim_id,
            status="UNVERIFIED",
            supporting_evidence_ids=[],
            contradicting_evidence_ids=[],
            confidence=0.0,
            reasoning=f"Parse error: {exc}",
        )


def node(state: CourtroomState) -> CourtroomState:
    """
    Fact Checker node: evaluates every claim independently.
    Populates state["fact_checks"].
    """
    case_id = state["case_id"]
    claims_raw = state.get("claims", [])

    fact_checks: List[FactCheck] = []
    for claim_data in claims_raw:
        claim = Claim.model_validate(claim_data) if isinstance(claim_data, dict) else claim_data
        fc = check_claim(claim, case_id)
        fact_checks.append(fc)
        logger.info(
            "Fact check: claim=%r → status=%s confidence=%.2f",
            claim.claim_id, fc.status, fc.confidence,
        )

    return {
        **state,
        "fact_checks": [fc.model_dump() for fc in fact_checks],
    }
