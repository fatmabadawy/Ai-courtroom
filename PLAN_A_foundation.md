# PLAN_A — Foundation, Database & Infrastructure

**Owns:** `backend/app/database/`, `docker-compose.yml`, repo scaffold, auth wiring, `data/demo_cases/case_001/`, `.env.example`.
**Read first:** `INTERFACES.md` §1, §2, §8.
**Blocks nobody for long** — your job in week 1 is to unblock B/C/D/E as fast as possible, not to gold-plate.

This corresponds to Phases 1–2 of the master `IMPLEMENTATION_PLAN.md`.

## Day 1 priority (do this before anything else)

1. Repo scaffold matching `IMPLEMENTATION_PLAN.md §32` — empty dirs with `.gitkeep` so B/C/D/E can start committing into their own folders immediately without touching yours.
2. Post the exact DDL from `IMPLEMENTATION_PLAN.md §8` as a migration file (`backend/app/database/migrations/0001_init.sql`) — this alone unblocks everyone, since B/C/D can spin up their own local pgvector container against this DDL even before your hosted Supabase project exists.
3. `.env.example` per master plan §45.

## Tasks

- [ ] Create Supabase project (or local stack — decide and document in `docs/deployment.md`, per master §31).
- [ ] Apply migration `0001_init.sql`; enable `pgvector` extension; create the HNSW index on `document_chunks.embedding`.
- [ ] Row Level Security policies on all case-scoped tables (master §8) — write one manual test per table proving cross-user access is blocked.
- [ ] `backend/app/database/client.py` — a thin typed wrapper others import (`get_case(case_id)`, `get_supabase_client()`) so B/C/D/E never hand-roll their own Supabase client config.
- [ ] Supabase Auth wiring: register/login/refresh, JWT validation dependency for FastAPI (`backend/app/database/auth.py`) — E will import this directly into their routers.
- [ ] `docker-compose.yml` with service stubs for `frontend`, `backend`, `worker`, `n8n` (empty/placeholder builds — B/C/D/E fill in their own Dockerfiles later, you just own the top-level file and merge their additions).
- [ ] Seed script + fixture per `INTERFACES.md §8`: `data/demo_cases/case_001/` with 2–3 short synthetic documents and a `expected_results.json` documenting which claim should end up `CONTRADICTED` / `SUPPORTED` — hand this to B/C/D on day 2.
- [ ] CI pipeline skeleton (lint + unit test runner) that others' test files plug into.

## Interfaces you must ship (per `INTERFACES.md`)

- Frozen DDL (§2) — do not rename columns/tables after day 2 without a team notice; everyone else's code references these names verbatim.
- `database/client.py` public functions used by B (insert documents/evidence), C (read/write cases/claims/arguments), D (write fact_checks/evidence_quality/verdicts), E (everything, via API layer).
- The synthetic fixture case (§8) with its `expected_results.json`.

## Testing

- Migration applies cleanly on a fresh DB (CI job).
- RLS manual test suite (one query per table, as a different user, expect 0 rows / permission error).
- Fixture case loads without error and matches `expected_results.json` shape.

## Acceptance criteria

- [ ] `docker compose up` starts an empty-but-running stack
- [ ] All tables from master §8 exist with correct FKs/indexes
- [ ] RLS blocks cross-user access (tested)
- [ ] `data/demo_cases/case_001/` present and loadable
- [ ] `.env.example` complete and accurate
- [ ] B, C, D, E have each successfully connected to your DB (or the local pgvector fallback) by end of week 1 — this is your real success metric, not just "schema exists"

## Integration notes

You are the one person nobody is waiting on for logic, only for infrastructure — ship the DDL and fixture case within the first 24–48 hours even if RLS/auth polish comes later, so the other four aren't idle.
