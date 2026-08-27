# PLAN_C — Case Intake, Prosecution & Defense Agents + LangGraph Skeleton

**Owns:** `backend/app/agents/intake.py`, `prosecution.py`, `defense.py`, `backend/app/graph/` (skeleton — shared with D, see merge protocol).
**Read first:** `INTERFACES.md` §3, §4, §5, §6.
**Depends on:** B's `retrieve_mock.py` (day 2) → later B's real `retrieve()`.

This corresponds to Phases 5–6 of the master `IMPLEMENTATION_PLAN.md` (§5, §12, §13, §33 for full detail).

## Day 1–2 priority

1. Set `USE_MOCK_RAG=true` and import `rag.retrieve_mock` per `INTERFACES.md §6` — don't wait for B's real implementation.
2. Create `backend/app/graph/state.py` with the exact `CourtroomState` TypedDict from `INTERFACES.md §4` — this is the shared file D also touches, so get it right and stable early.
3. Create `backend/app/graph/build_graph.py` with the skeleton: `START → INTAKE → EVIDENCE → PARALLEL(PROSECUTION, DEFENSE) → PASSTHROUGH_STUB → END`. Announce in the team channel once pushed so D knows it's safe to build on top of.

## Tasks — Case Intake Agent

- [ ] Pydantic `StructuredCase` output (already defined in `INTERFACES.md §3` — don't redefine).
- [ ] System prompt per master §5: extract only from provided text, populate `unknowns`/`contradictions` instead of guessing, never reference an `evidence_id` that doesn't exist.
- [ ] Validation: parse with `pydantic`, one retry on failure with the validation error appended, fail-soft to `NEEDS_REVIEW` status on second failure (never crash the graph).
- [ ] Strip any `evidence_id` in the output that doesn't exist in the retrieved evidence set (anti-hallucination check, log it).

## Tasks — Prosecution / Defense Agents

- [ ] Both follow the `Argument` schema from `INTERFACES.md §3` — `side` field distinguishes them, everything else is shared logic (you can genuinely share one internal helper function parameterized by `side`).
- [ ] Each issues its own RAG queries per open claim/legal question via `rag.retrieve()`.
- [ ] Enforce in code (not just prompt): `confidence > 0.3` requires non-empty `evidence_ids`.
- [ ] Defense reads `state["prosecution_arguments"]` and sets `responds_to_argument_id` when directly rebutting a specific prosecution argument.
- [ ] Both must be able to emit "no evidence found" (empty `evidence_ids`, low confidence) rather than invent something — write a fixture that specifically exercises this path.

## Tasks — Graph skeleton

- [ ] `EVIDENCE` node: given `state["claims"]`/`legal_questions`, calls `retrieve()` and populates `state["evidence_ids"]` before Prosecution/Defense run.
- [ ] `PARALLEL(PROSECUTION, DEFENSE)` — LangGraph parallel branch execution merging back into one state before the stub.
- [ ] `PASSTHROUGH_STUB` — a no-op node D will replace; keep it trivially removable (one line).
- [ ] `graph/run.py` skeleton: `run_trial(case_id)` that builds and invokes the graph up through your nodes and returns state (even though it's incomplete until D adds theirs) — this lets E start integration-testing against a partial-but-real graph instead of only the mock.

## Interfaces you must ship

- `agents/intake.py`, `prosecution.py`, `defense.py`, each exposing a `node(state) -> state` function per `INTERFACES.md §4` node convention.
- `graph/state.py`, `graph/build_graph.py` (skeleton), `graph/run.py` (skeleton) — D extends these, doesn't replace them.

## Testing

- Agent tests against A's fixture case (`case_001`): Intake produces a schema-valid `StructuredCase`; Prosecution/Defense produce non-empty `Argument` lists with evidence grounding on the fixture's designed-to-be-supported claim.
- Fixture with a deliberately unsupported claim → confirm "no evidence found" path, not fabrication.
- Full retry-then-fail-soft path tested with a forced malformed-output scenario (mock the LLM call to return invalid JSON once).

## Acceptance criteria (mirrors master §39 Phases 5–6)

- [ ] Valid `StructuredCase` JSON on the fixture case
- [ ] `unknowns`/`contradictions` populated where the fixture is designed to contain them
- [ ] Prosecution and Defense both produce evidence-grounded `Argument`s
- [ ] "No evidence found" path exercised in a test
- [ ] Graph skeleton runs end-to-end through your three nodes without error

## Integration notes

Once B ships the real `retrieve()`, flip `USE_MOCK_RAG=false` and rerun your full test suite unchanged — if it breaks, the mismatch is between B's real output and the `EvidenceResult` schema, flag it in `INTERFACES.md`, don't silently patch around it locally. Keep `build_graph.py` edits small and announced (see `INTERFACES.md §5`) since D is editing the same file.
