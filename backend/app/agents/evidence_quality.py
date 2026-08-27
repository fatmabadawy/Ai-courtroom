"""
backend/app/agents/evidence_quality.py
────────────────────────────────────────
Evidence Quality Agent — Plan D.

Responsibilities:
  - Score every evidence item referenced by any argument on five dimensions:
      reliability, directness, relevance, corroboration, recency.
  - Compute a documented weighted composite_score.
  - Attach the DISCLAIMER constant to the output (one shared constant,
    not repeated strings).
  - Populate state["evidence_quality"].

Composite score formula (PLAN_D: "documented weighted average"):
  composite = (
      W_RELIABILITY  * reliability  +
      W_DIRECTNESS   * directness   +
      W_RELEVANCE    * relevance    +
      W_CORROBORATION* corroboration+
      W_RECENCY      * recency
  )
  Weights sum to 1.0 and are defined as module-level constants so they
  appear in code review and are auditable.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Set

from backend.app.graph.state import CourtroomState
from backend.app.llm_client import get_llm_response
from backend.app.models.schemas import (
    Argument,
    EvidenceQualityScore,
    EvidenceResult,
)
from backend.app.rag.retrieve_mock import get_evidence_by_id

logger = logging.getLogger(__name__)

# ── Shared disclaimer (PLAN_D: "put it in one shared constant") ────────────────
QUALITY_DISCLAIMER: str = (
    "Evidence quality scores are produced by system heuristics and are not "
    "legal standards or professional forensic assessments."
)

# ── Composite score weights (must sum to 1.0) ──────────────────────────────────
W_RELIABILITY: float = 0.30
W_DIRECTNESS: float = 0.25
W_RELEVANCE: float = 0.20
W_CORROBORATION: float = 0.15
W_RECENCY: float = 0.10
METHODOLOGY_VERSION: str = "v1"

assert abs(
    W_RELIABILITY + W_DIRECTNESS + W_RELEVANCE + W_CORROBORATION + W_RECENCY - 1.0
) < 1e-9, "Composite score weights must sum to 1.0"

# ── Prompt ─────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = f"""You are an expert evidence quality assessor.
Score the given evidence item on five dimensions, each 0.0–1.0:
  reliability   — source credibility and accuracy
  directness    — how directly it addresses the central dispute
  relevance     — how relevant it is to the claims in the case
  corroboration — whether it is corroborated by other sources
  recency       — how recent and current the evidence is

Return a single JSON object:
{{
  "evidence_id": str,
  "reliability": float,
  "directness": float,
  "relevance": float,
  "corroboration": float,
  "recency": float,
  "authenticity_notes": str | null
}}

Important:
- All scores must be between 0.0 and 1.0.
- authenticity_notes is optional (null if nothing to note).
- Return ONLY the JSON object.
- Disclaimer that will be attached automatically: "{QUALITY_DISCLAIMER}"
"""

_USER_PROMPT_TEMPLATE = """Evidence item:
  evidence_id: {evidence_id}
  source_type: {source_type}
  content: {content}

Score this evidence."""


def _compute_composite(scores: dict) -> float:
    return (
        W_RELIABILITY * scores["reliability"]
        + W_DIRECTNESS * scores["directness"]
        + W_RELEVANCE * scores["relevance"]
        + W_CORROBORATION * scores["corroboration"]
        + W_RECENCY * scores["recency"]
    )


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _mock_score(evidence_id: str, ev: EvidenceResult | None) -> str:
    """Deterministic mock scores based on evidence source_type."""
    if ev is None:
        return json.dumps({
            "evidence_id": evidence_id,
            "reliability": 0.5,
            "directness": 0.5,
            "relevance": 0.5,
            "corroboration": 0.3,
            "recency": 0.5,
            "authenticity_notes": None,
        })

    base = {
        "USER_PROVIDED": dict(reliability=0.85, directness=0.8, relevance=0.9,
                              corroboration=0.7, recency=0.75),
        "PUBLIC_LEGAL_SOURCE": dict(reliability=0.9, directness=0.75, relevance=0.8,
                                    corroboration=0.8, recency=0.6),
        "WEB_SOURCE": dict(reliability=0.5, directness=0.6, relevance=0.65,
                           corroboration=0.4, recency=0.8),
        "SYNTHETIC": dict(reliability=0.7, directness=0.7, relevance=0.7,
                          corroboration=0.5, recency=0.7),
    }.get(ev.source_type, dict(reliability=0.5, directness=0.5, relevance=0.5,
                                corroboration=0.5, recency=0.5))

    return json.dumps({
        "evidence_id": evidence_id,
        **base,
        "authenticity_notes": None,
    })


def score_evidence(evidence_id: str) -> EvidenceQualityScore:
    """
    Pure function: score a single evidence item.
    Testable standalone without the full graph.
    """
    ev = get_evidence_by_id(evidence_id)
    mock_resp = _mock_score(evidence_id, ev)

    content = ev.content if ev else "(evidence content not found)"
    source_type = ev.source_type if ev else "SYNTHETIC"

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        evidence_id=evidence_id,
        source_type=source_type,
        content=content,
    )

    raw = get_llm_response(
        _SYSTEM_PROMPT,
        user_prompt,
        mock_response=mock_resp,
    )

    try:
        data = json.loads(raw)
        # Clamp all scores
        for field in ("reliability", "directness", "relevance", "corroboration", "recency"):
            data[field] = _clamp(float(data.get(field, 0.5)))

        composite = _compute_composite(data)
        return EvidenceQualityScore(
            evidence_id=evidence_id,
            reliability=data["reliability"],
            directness=data["directness"],
            relevance=data["relevance"],
            corroboration=data["corroboration"],
            recency=data["recency"],
            authenticity_notes=data.get("authenticity_notes"),
            composite_score=_clamp(composite),
            methodology_version=METHODOLOGY_VERSION,
        )
    except Exception as exc:
        logger.error("Evidence quality parse error for %r: %s", evidence_id, exc)
        return EvidenceQualityScore(
            evidence_id=evidence_id,
            reliability=0.5,
            directness=0.5,
            relevance=0.5,
            corroboration=0.5,
            recency=0.5,
            authenticity_notes=f"Scoring error: {exc}",
            composite_score=0.5,
            methodology_version=METHODOLOGY_VERSION,
        )


def _collect_evidence_ids(state: CourtroomState) -> Set[str]:
    """Gather all evidence IDs referenced by any argument in the state."""
    ids: Set[str] = set()
    for arg_data in state.get("prosecution_arguments", []):
        arg = Argument.model_validate(arg_data) if isinstance(arg_data, dict) else arg_data
        ids.update(arg.evidence_ids)
    for arg_data in state.get("defense_arguments", []):
        arg = Argument.model_validate(arg_data) if isinstance(arg_data, dict) else arg_data
        ids.update(arg.evidence_ids)
    # Also score top-level evidence from the state
    ids.update(state.get("evidence_ids", []))
    return ids


def node(state: CourtroomState) -> CourtroomState:
    """
    Evidence Quality node: score every evidence item referenced by any argument.
    Populates state["evidence_quality"] as Dict[str, EvidenceQualityScore].
    """
    evidence_ids = _collect_evidence_ids(state)
    quality_map: Dict[str, EvidenceQualityScore] = {}

    for eid in sorted(evidence_ids):
        score = score_evidence(eid)
        quality_map[eid] = score
        logger.info(
            "Evidence quality: %r → composite=%.3f",
            eid, score.composite_score,
        )

    return {
        **state,
        "evidence_quality": {k: v.model_dump() for k, v in quality_map.items()},
    }
