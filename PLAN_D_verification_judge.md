# PLAN_D — Fact Checker, Evidence Quality, Cross-Examination, Judge & Human-in-the-Loop

**Owns:** `backend/app/agents/fact_checker.py`, `evidence_quality.py`, `cross_examiner.py`, `judge.py`; extends `backend/app/graph/` (shared with C, see merge protocol); owns LangGraph checkpointing config.
**Read first:** `INTERFACES.md` §3, §4, §5, §6, §7.
**Depends on:** C's `graph/state.py` + `build_graph.py` skeleton (wait for C's "safe to build on" announcement, day 2–3), B's `retrieve()`/mock.

This corresponds to Phases 7–11 of the master `IMPLEMENTATION_PLAN.md` (§14–§18, §16 for the cross-exam loop, §17 for human-in-the-loop, §33 for graph/checkpoint detail).

## Day 1–2 priority

While waiting on C's graph skeleton, start on the agent *logic* in isolation (each is a pure function of `Argument`/`Claim` lists + retrieved evidence, testable without the graph at all). Use `rag.retrieve_mock` and hand-built fixture `Argument` lists so you're not blocked.

## Tasks — Fact Checker

- [ ] `FactCheck` schema output per `INTERFACES.md §3`.
- [ ] Runs **independent** retrieval — do not simply reuse the `evidence_ids` already cited by Prosecution/Defense; call `retrieve()` fresh per claim.
- [ ] Status enum exactly `SUPPORTED | CONTRADICTED | PARTIALLY_SUPPORTED | UNVERIFIED`.
- [ ] Test against A's fixture: the claim marked `CONTRADICTED` in `expected_results.json` must come out `CONTRADICTED`.

## Tasks — Evidence Quality

- [ ] Score every evidence item referenced by any argument on: reliability, directness, relevance, corroboration, recency (master §15).
- [ ] `composite_score` = documented weighted average; weights + `methodology_version` stored, not hardcoded magic numbers buried in code.
- [ ] Every place a score is surfaced (including in your own return payload) carries the "system heuristics, not legal standards" disclaimer string — put it in one shared constant, don't restring it.

## Tasks — Cross-Examination (bounded loop)

- [ ] Implement as the actual sub-loop in master §16: select weakest/contested argument → generate challenge → route to responding side → Fact Checker re-evaluates → outcome recorded → round += 1.
- [ ] Hard termination: `round >= MAX_ROUNDS` (default 3, config value) **or** confidence deltas below threshold (convergence) **or** no contested arguments remain. Write a test that forces a fixture designed to never converge and asserts the loop still terminates.
- [ ] Each round appends a new `CrossExaminationRound`; never mutate/delete prior rounds (needed for replay later, owned by E).

## Tasks — Judge

- [ ] Consumes full `CourtroomState`; produces `Verdict` per `INTERFACES.md §3`, including the disclaimer field.
- [ ] Hard validation: every `evidence_id` in `supporting_evidence_ids`/`opposing_evidence_ids` must exist in `state["evidence_ids"]` — reject/flag otherwise, don't trust the LLM's citations blindly.
- [ ] Three judge profiles (strict/balanced/skeptical) as prompt-level configuration only, run against **identical** evidence — write a test asserting all three produce internally consistent but distinct output on the fixture.

## Tasks — Human-in-the-loop + checkpointing

- [ ] LangGraph checkpointer backed by Postgres (A's DB) so state survives process restarts.
- [ ] Conditional edge `NEEDS_HUMAN_INPUT?` and the interrupt/resume mechanics (verify against the pinned LangGraph version's current API before writing this — the interrupt pattern has changed across releases).
- [ ] `graph/run.py`: fill in `resume_trial(case_id, intervention)` per `INTERFACES.md §7`.
- [ ] When new evidence arrives mid-trial, only re-run Prosecution/Defense/Fact-Check for claims flagged `needs_reassessment` (similarity match between new evidence and existing claims) — not the whole case, for cost control.

## Tasks — Graph completion

- [ ] Replace C's `PASSTHROUGH_STUB` in `build_graph.py` with: `FACT_CHECK → EVIDENCE_QUALITY → CROSS_EXAMINATION → conditional(NEEDS_HUMAN_INPUT) → JUDGE → END`.
- [ ] Ship `run_mock.py` per `INTERFACES.md §7` **as soon as your schema is stable, even before the real graph is done** — this is your highest-leverage early deliverable for unblocking E, same principle as B's `retrieve_mock.py`.

## Testing

- Each agent has a standalone unit test against hand-built fixtures (not dependent on C's graph being done).
- Full-loop test against A's fixture case once C's skeleton + your nodes are merged: confirm the `CONTRADICTED`/`SUPPORTED` claims match `expected_results.json` all the way through to the verdict.
- Cross-exam non-convergence fixture (forced infinite-disagreement scenario) → confirm hard termination at `MAX_ROUNDS`.
- Human intervention test: inject new evidence mid-trial, confirm only affected claims re-run.

## Acceptance criteria (mirrors master §39 Phases 7–11)

- [ ] Fact Checker correct on fixture's `CONTRADICTED`/`SUPPORTED` claims
- [ ] Every evidence item scored, disclaimer present
- [ ] Cross-exam loop always terminates within `MAX_ROUNDS`
- [ ] Verdict cites only real `evidence_id`s (programmatically validated)
- [ ] All three judge profiles differ meaningfully but consistently
- [ ] Trial can be paused and resumed via `graph/run.py` functions
- [ ] `run_mock.py` shipped early, real graph passes the same tests as the mock once ready

## Integration notes

Coordinate `build_graph.py` edits with C via the merge protocol in `INTERFACES.md §5` — small, announced diffs only. Once your real graph is done, E flips `USE_MOCK_GRAPH=false`; if that breaks E's tests, the drift is between your `run_trial`/`resume_trial` output and the `CourtroomState`/`Verdict` schema — fix the implementation to match the frozen contract rather than asking E to adapt.
