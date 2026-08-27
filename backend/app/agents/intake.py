"""
backend/app/agents/intake.py
─────────────────────────────
Case Intake Agent — Plan C.

Responsibilities:
  1. Call the LLM to parse raw case text into a StructuredCase.
  2. Validate with Pydantic; retry once on failure with the error appended.
  3. Fail-soft on second failure:
       - All claims set to UNVERIFIED  (DEVIATION #6: NEEDS_REVIEW not in
         the Claim.status Literal enum; see implementation_plan.md)
       - Entry added to unresolved_questions
  4. Strip any evidence_id in the output that is not in the retrieved
     evidence set (anti-hallucination guard); log each stripping.

Node signature follows INTERFACES.md §4 convention:
    def node(state: CourtroomState) -> CourtroomState
"""

from __future__ import annotations

import json
import logging
from typing import List

from pydantic import ValidationError

from backend.app.graph.state import CourtroomState
from backend.app.llm_client import get_llm_response
from backend.app.models.schemas import Claim, StructuredCase
from backend.app.rag.retrieve import retrieve

logger = logging.getLogger(__name__)

# ── Prompt templates ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a precise legal case analyst.
Your task is to extract structured information from a case description and
return it as valid JSON matching the StructuredCase schema.

Rules you MUST follow:
- Extract ONLY information explicitly present in the text — populate
  `unknowns` and `contradictions` instead of guessing or inferring.
- NEVER reference an evidence_id that you haven't been given in the
  evidence list below.
- All field names and Literal values must match the schema exactly.
- `provenance_type` must be one of: USER_PROVIDED, PUBLIC_LEGAL_SOURCE, SYNTHETIC.
- `made_by` on each Claim must be one of: prosecution, defense, intake.
- `status` on each Claim must be one of:
  SUPPORTED, CONTRADICTED, PARTIALLY_SUPPORTED, UNVERIFIED.
- Return ONLY the JSON object — no markdown, no prose.

StructuredCase schema fields:
{
  "case_id": str,
  "title": str,
  "description": str,
  "parties": [{"party_id": str, "name": str, "role": str, "description": str|null}],
  "claims": [{"claim_id": str, "statement": str, "made_by": str,
              "related_evidence_ids": [str], "status": str}],
  "events": [{"event_id": str, "description": str, "date": str|null,
               "evidence_ids": [str]}],
  "legal_questions": [str],
  "evidence_ids": [str],
  "unknowns": [str],
  "contradictions": [str],
  "provenance_type": str
}"""

_USER_PROMPT_TEMPLATE = """Case ID: {case_id}

Case Description:
{case_description}

Available evidence IDs (ONLY reference these):
{evidence_ids}

Return a JSON object matching the StructuredCase schema."""

_RETRY_SUFFIX = """

The previous attempt returned invalid JSON or failed schema validation.
Validation error:
{error}

Please correct the output and return a valid JSON object."""

# ── Mock response (used when USE_MOCK_LLM=true) ───────────────────────────────

def _build_mock_response(case_id: str, evidence_ids: List[str]) -> str:
    """Returns a deterministic, schema-valid StructuredCase JSON string."""
    ev_str = json.dumps(evidence_ids)
    return json.dumps({
        "case_id": case_id,
        "title": "ACME Corp v. WidgetCo — Breach of Supply Agreement",
        "description": (
            "ACME Corp alleges WidgetCo materially breached a supply agreement. "
            "WidgetCo invokes force majeure."
        ),
        "parties": [
            {"party_id": "P1", "name": "ACME Corp", "role": "plaintiff", "description": None},
            {"party_id": "P2", "name": "WidgetCo", "role": "defendant", "description": None},
            {"party_id": "P3", "name": "Marcus Chen", "role": "witness", "description": "Supply-chain auditor"},
        ],
        "claims": [
            {
                "claim_id": "CL-001",
                "statement": "ACME Corp made NO payment to WidgetCo prior to the alleged breach date.",
                "made_by": "intake",
                "related_evidence_ids": [evidence_ids[1]] if len(evidence_ids) > 1 else [],
                "status": "UNVERIFIED",
            },
            {
                "claim_id": "CL-002",
                "statement": "WidgetCo's delay was excused by a valid force majeure event.",
                "made_by": "intake",
                "related_evidence_ids": evidence_ids[:3],
                "status": "UNVERIFIED",
            },
        ],
        "events": [
            {
                "event_id": "EV-EVT-1",
                "description": "Contract signed between ACME Corp and WidgetCo",
                "date": None,
                "evidence_ids": [evidence_ids[0]] if evidence_ids else [],
            }
        ],
        "legal_questions": [
            "Did WidgetCo materially breach the supply agreement?",
            "Is the force majeure clause in §9.3 applicable?",
        ],
        "evidence_ids": evidence_ids,
        "unknowns": ["Exact damages amount not specified in description"],
        "contradictions": [],
        "provenance_type": "SYNTHETIC",
    })


# ── Core parsing logic ─────────────────────────────────────────────────────────

def _parse_structured_case(raw_json: str) -> StructuredCase:
    """Parse and validate LLM output as StructuredCase."""
    data = json.loads(raw_json)  # raises json.JSONDecodeError if not valid JSON
    return StructuredCase.model_validate(data)  # raises ValidationError if schema mismatch


def _strip_hallucinated_evidence_ids(
    case: StructuredCase,
    valid_ids: set[str],
) -> StructuredCase:
    """
    Remove any evidence_id not in the retrieved set from the case output.
    Mutates a copy; logs each removal.
    """
    cleaned_evidence_ids = []
    for eid in case.evidence_ids:
        if eid in valid_ids:
            cleaned_evidence_ids.append(eid)
        else:
            logger.warning(
                "Intake hallucination guard: stripped evidence_id=%r "
                "(not in retrieved set) from case_id=%r",
                eid, case.case_id,
            )

    cleaned_claims = []
    for claim in case.claims:
        cleaned_rel = [eid for eid in claim.related_evidence_ids if eid in valid_ids]
        stripped = set(claim.related_evidence_ids) - set(cleaned_rel)
        if stripped:
            logger.warning(
                "Intake hallucination guard: stripped %s from claim %r "
                "related_evidence_ids",
                stripped, claim.claim_id,
            )
        cleaned_claims.append(claim.model_copy(update={"related_evidence_ids": cleaned_rel}))

    cleaned_events = []
    for event in case.events:
        cleaned_ev_ids = [eid for eid in event.evidence_ids if eid in valid_ids]
        cleaned_events.append(event.model_copy(update={"evidence_ids": cleaned_ev_ids}))

    return case.model_copy(update={
        "evidence_ids": cleaned_evidence_ids,
        "claims": cleaned_claims,
        "events": cleaned_events,
    })


# ── Node ───────────────────────────────────────────────────────────────────────

def node(state: CourtroomState) -> CourtroomState:
    """
    Intake node: parse case_description into StructuredCase, populate state.

    Retry behaviour (PLAN_C):
    - On Pydantic/JSON parse failure: append error to prompt and retry once.
    - On second failure: fail-soft (DEVIATION #6 in implementation_plan.md):
        all claims → UNVERIFIED, entry in unresolved_questions.
    """
    case_id = state["case_id"]
    case_description = state["case_description"]

    # Step 1: retrieve evidence to build the valid-ID set.
    retrieved = retrieve(case_id, case_description)
    valid_ids = {r.evidence_id for r in retrieved}

    evidence_ids_list = sorted(valid_ids)
    mock_resp = _build_mock_response(case_id, evidence_ids_list)

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        case_id=case_id,
        case_description=case_description,
        evidence_ids=", ".join(evidence_ids_list),
    )

    # Step 2: first attempt
    raw = get_llm_response(
        _SYSTEM_PROMPT,
        user_prompt,
        mock_response=mock_resp,
    )

    structured_case: StructuredCase | None = None
    parse_error: str | None = None

    try:
        structured_case = _parse_structured_case(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        parse_error = str(exc)
        logger.warning("Intake first attempt failed (case=%r): %s", case_id, parse_error)

    # Step 3: one retry on failure
    if structured_case is None:
        retry_prompt = user_prompt + _RETRY_SUFFIX.format(error=parse_error)
        raw2 = get_llm_response(
            _SYSTEM_PROMPT,
            retry_prompt,
            mock_response=mock_resp,  # mock always returns valid JSON
        )
        try:
            structured_case = _parse_structured_case(raw2)
            logger.info("Intake retry succeeded (case=%r).", case_id)
        except (json.JSONDecodeError, ValidationError) as exc2:
            parse_error = str(exc2)
            logger.error(
                "Intake second attempt failed (case=%r): %s — fail-soft.",
                case_id, parse_error,
            )

    # Step 4: fail-soft path (DEVIATION #6)
    if structured_case is None:
        logger.error("Intake fail-soft triggered for case=%r.", case_id)
        fail_soft_unresolved = list(state.get("unresolved_questions", []))
        fail_soft_unresolved.append(
            f"NEEDS_REVIEW: intake parse failed twice for case_id={case_id!r}. "
            f"Last error: {parse_error}"
        )
        # Return state with minimal changes — downstream nodes will see empty claims.
        return {
            **state,
            "evidence_ids": evidence_ids_list,
            "unresolved_questions": fail_soft_unresolved,
        }

    # Step 5: strip hallucinated evidence_ids
    structured_case = _strip_hallucinated_evidence_ids(structured_case, valid_ids)

    # Step 6: populate state from StructuredCase
    updated_state = {
        **state,
        "parties": [p.model_dump() for p in structured_case.parties],
        "claims": [c.model_dump() for c in structured_case.claims],
        "legal_questions": structured_case.legal_questions,
        "evidence_ids": structured_case.evidence_ids,
        "unresolved_questions": list(state.get("unresolved_questions", []))
        + structured_case.unknowns,
    }

    return updated_state
