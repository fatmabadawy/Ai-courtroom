# INTERFACES.md — Shared Contract for AI Courtroom (5-way parallel build)

> **Read this before touching any sub-plan.** This file is the single source of truth for every schema, table, and function signature that crosses a team-member boundary. If two people's code both compile against this file, their work integrates without a merge negotiation. Anyone who needs to change something here must post the diff to the whole team before merging — this file changes rarely and deliberately.

Parent document: `IMPLEMENTATION_PLAN.md` (sections referenced below by number, e.g. §8 = Database schema).

---

## 1. Ownership map (which member's plan owns which file/dir)

```
backend/app/database/       → A (schema, migrations, RLS, client helpers)
backend/app/ingestion/      → B
backend/app/rag/            → B
backend/app/agents/intake.py, prosecution.py, defense.py → C
backend/app/graph/          → C (skeleton) + D (adds nodes) — see §5 merge rule
backend/app/agents/fact_checker.py, evidence_quality.py,
  cross_examiner.py, judge.py → D
backend/app/api/            → E
frontend/                   → E
n8n/                        → E
docker-compose.yml          → A (owns the file; others add their service block)
```

No two members write to the same file. `graph/build_graph.py` is the one shared file — see §5 for the merge protocol.

---

## 2. Database schema (owned by A, referenced by everyone)

Full DDL is in `IMPLEMENTATION_PLAN.md §8`. Every member builds against **these exact table/column names** — do not invent alternate names locally. Key tables each member touches:

- A: all tables (creates them)
- B: `documents`, `document_chunks`, `sources`, `evidence`
- C: `cases`, `case_parties`, `claims`, `arguments`
- D: `fact_checks`, `evidence_quality`, `cross_examinations`, `verdicts`, `verdict_evidence`
- E: reads/writes across all tables via the API layer; owns `agent_messages`, `case_events`

**Until A's live Supabase instance exists**, everyone runs the DDL from §8 against a local Postgres+pgvector container (`docker run pgvector/pgvector:pg16` or similar) so B/C/D/E are never blocked waiting on A's hosted setup — only on the schema *definition*, which is already frozen in §8.

---

## 3. Core Pydantic schemas (verbatim — copy into `backend/app/models/schemas.py`, owned jointly, edits require team notice)

```python
from typing import List, Optional, Literal
from datetime import date
from pydantic import BaseModel

class Party(BaseModel):
    party_id: str
    name: str
    role: Literal["plaintiff", "defendant", "witness", "other"]
    description: Optional[str] = None

class CaseEvent(BaseModel):
    event_id: str
    description: str
    date: Optional[date] = None
    evidence_ids: List[str] = []

class Claim(BaseModel):
    claim_id: str
    statement: str
    made_by: Literal["prosecution", "defense", "intake"]
    related_evidence_ids: List[str] = []
    status: Literal["SUPPORTED", "CONTRADICTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"] = "UNVERIFIED"

class StructuredCase(BaseModel):
    case_id: str
    title: str
    description: str
    parties: List[Party] = []
    claims: List[Claim] = []
    events: List[CaseEvent] = []
    legal_questions: List[str] = []
    evidence_ids: List[str] = []
    unknowns: List[str] = []
    contradictions: List[str] = []
    provenance_type: Literal["USER_PROVIDED", "PUBLIC_LEGAL_SOURCE", "SYNTHETIC"]

class EvidenceResult(BaseModel):
    """What rag.retrieve() returns — B's output contract."""
    evidence_id: str
    content: str
    source_type: Literal["USER_PROVIDED", "PUBLIC_LEGAL_SOURCE", "WEB_SOURCE", "SYNTHETIC"]
    document_id: Optional[str] = None
    document_page: Optional[int] = None
    relevance_score: float

class Argument(BaseModel):
    claim_id: str
    argument: str
    evidence_ids: List[str]
    source_ids: List[str] = []
    confidence: float
    side: Literal["prosecution", "defense"]
    round: int = 1
    responds_to_argument_id: Optional[str] = None

class FactCheck(BaseModel):
    claim_id: str
    status: Literal["SUPPORTED", "CONTRADICTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"]
    supporting_evidence_ids: List[str]
    contradicting_evidence_ids: List[str]
    confidence: float
    reasoning: str

class EvidenceQualityScore(BaseModel):
    evidence_id: str
    reliability: float
    directness: float
    relevance: float
    corroboration: float
    recency: float
    authenticity_notes: Optional[str] = None
    composite_score: float
    methodology_version: str = "v1"

class CrossExaminationRound(BaseModel):
    round: int
    challenger: Literal["cross_examiner"]
    target_argument_id: str
    question: str
    response: str
    outcome: Literal["strengthened", "weakened", "unchanged"]

class JudgeProfile(BaseModel):
    name: Literal["strict", "balanced", "skeptical"]

class Verdict(BaseModel):
    finding: str
    supporting_evidence_ids: List[str]
    opposing_evidence_ids: List[str]
    unresolved_questions: List[str]
    reasoning: str
    confidence: float
    judge_profile: str
    disclaimer: str = (
        "This is an educational/research simulation and is not legal advice "
        "or a real legal decision-maker."
    )

class HumanIntervention(BaseModel):
    new_document_ids: List[str]
    affected_claim_ids: List[str]
    submitted_at: str
```

---

## 4. LangGraph state (verbatim — copy into `backend/app/graph/state.py`, owned by C, edits require team notice)

```python
from typing import TypedDict, List, Dict, Optional

class CourtroomState(TypedDict):
    case_id: str
    case_description: str
    parties: List[Party]
    claims: List[Claim]
    legal_questions: List[str]
    evidence_ids: List[str]
    prosecution_arguments: List[Argument]
    defense_arguments: List[Argument]
    fact_checks: List[FactCheck]
    evidence_quality: Dict[str, EvidenceQualityScore]
    cross_examinations: List[CrossExaminationRound]
    unresolved_questions: List[str]
    human_intervention: Optional[HumanIntervention]
    judge_configuration: JudgeProfile
    verdict: Optional[Verdict]
    round: int
```

**Node convention (every agent, C's and D's alike, must follow this signature):**
```python
def node(state: CourtroomState) -> CourtroomState:
    ...
    return updated_state
```
This is what makes nodes swappable in `build_graph.py` regardless of who wrote them.

---

## 5. `graph/build_graph.py` — shared-file merge protocol

C creates this file first (Phase 1 of C's plan) with the linear skeleton `START → INTAKE → EVIDENCE → PARALLEL(PROSECUTION, DEFENSE) → [PASSTHROUGH] → END`, where `[PASSTHROUGH]` is a no-op stub node. D replaces `[PASSTHROUGH]` with `FACT_CHECK → EVIDENCE_QUALITY → CROSS_EXAMINATION → conditional(NEEDS_HUMAN_INPUT) → JUDGE → END` once their nodes exist. **Rule: only one of C/D edits this file in a given day; announce in the team channel before editing.** Both should keep node functions themselves in their own owned files (`agents/*.py`) and only import + register them here, so the diff in this file is always small (a couple of `add_node`/`add_edge` lines).

---

## 6. B's RAG interface (what C and D code against, mocked until real)

```python
# backend/app/rag/retrieve.py — owned by B
def retrieve(
    case_id: str,
    query: str,
    top_k: int = 8,
    filters: Optional[dict] = None,   # e.g. {"evidence_type": "contract"}
) -> List[EvidenceResult]:
    ...
```

**Mock for C/D to use before B ships the real thing** (`backend/app/rag/retrieve_mock.py`, provided by B in the first 2 days):
```python
def retrieve(case_id, query, top_k=8, filters=None) -> List[EvidenceResult]:
    return [
        EvidenceResult(evidence_id="EV-MOCK-1", content="Sample contract clause...",
                        source_type="SYNTHETIC", document_id="DOC-MOCK-1",
                        document_page=1, relevance_score=0.9),
        EvidenceResult(evidence_id="EV-MOCK-2", content="Sample witness line...",
                        source_type="SYNTHETIC", document_id="DOC-MOCK-2",
                        document_page=2, relevance_score=0.8),
    ]
```
C and D import from `rag.retrieve` (real) or `rag.retrieve_mock` (temporary) behind a single flag/env var `USE_MOCK_RAG=true`, so swapping to the real implementation is a one-line change, not a rewrite.

---

## 7. C/D's graph invocation interface (what E codes against, mocked until real)

```python
# backend/app/graph/run.py — owned by C (skeleton) / D (fills in)
def run_trial(case_id: str) -> CourtroomState: ...
def resume_trial(case_id: str, intervention: Optional[HumanIntervention] = None) -> CourtroomState: ...
```

**Mock for E to use before C/D ship the real graph** (`backend/app/graph/run_mock.py`):
```python
def run_trial(case_id: str) -> CourtroomState:
    # returns a hardcoded but schema-valid CourtroomState with a populated Verdict
    ...
```
Same `USE_MOCK_GRAPH=true` flag pattern.

---

## 8. Synthetic fixture case (owned by A, used by everyone)

A ships one seeded synthetic case (`data/demo_cases/case_001/`) in Phase 1, containing: 2–3 short fake documents (contract, email, witness statement), pre-computed expected values (one claim that should end up `CONTRADICTED`, one `SUPPORTED`) so B/C/D can each write a deterministic test against the *same* fixture without waiting on each other's output.

---

## 9. Weekly integration checkpoint

Every Friday: pull latest from all 5 branches into an `integration` branch, run the full test suite (§35 of the master plan), flip all `USE_MOCK_*` flags to `false` one at a time and confirm nothing breaks. Any schema/interface change discovered mid-week that isn't reflected in this file gets added here immediately, not left tribal.
