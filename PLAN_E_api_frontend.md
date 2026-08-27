# PLAN_E — FastAPI Backend, React Frontend & n8n Automation

**Owns:** `backend/app/api/`, `frontend/`, `n8n/`.
**Read first:** `INTERFACES.md` §3, §6, §7.
**Depends on:** everyone, but every dependency has a mock — you should never be blocked.

This corresponds to Phases 12–16 of the master `IMPLEMENTATION_PLAN.md` (§26, §27, §25 for full detail).

## Day 1–3 priority

You have the most downstream dependencies of anyone, so lean hardest on the mocking strategy:
1. Use A's `database/client.py` (real, since A ships this early) for simple CRUD (cases, documents metadata).
2. Use B's `ingestion.ingest_document()` — real once B ships it (early), mock with a stub that just writes a `documents` row otherwise.
3. Use `graph.run_mock.run_trial()` / `resume_trial()` per `INTERFACES.md §7` for **everything trial-related** until C/D ship the real graph. This lets you build and fully test the entire trial API surface and the Courtroom/Verdict frontend screens against realistic, schema-valid fake data from week 1.

## Tasks — FastAPI endpoints (master §26)

- [ ] Auth: `POST /auth/register`, `/auth/login`, `/auth/refresh` — thin wrappers around A's `database/auth.py`.
- [ ] Cases: `POST/GET /cases`, `GET/DELETE /cases/{case_id}`.
- [ ] Documents: `POST/GET /cases/{case_id}/documents`, `GET /documents/{document_id}` — calls B's `ingest_document()`.
- [ ] Real case search: `POST /cases/search-public` (Mode B acquisition — see note below, can stub initially).
- [ ] Trial: `POST /trial/start`, `GET /trial/state`, `POST /trial/intervene`, `POST /trial/resume` — calls `graph.run_trial`/`resume_trial` (mock → real).
- [ ] Evidence: `GET /cases/{case_id}/evidence`, `GET /evidence/{evidence_id}`.
- [ ] Evidence graph: `GET /cases/{case_id}/evidence-graph` — joins `claims → claim_evidence → evidence → documents/sources` into a node/edge JSON payload.
- [ ] Replay: `GET /cases/{case_id}/replay` — reads `agent_messages` ordered by timestamp.
- [ ] Verdict: `GET /cases/{case_id}/verdict[s]`.
- [ ] Every endpoint: typed Pydantic request/response (reuse `INTERFACES.md §3` schemas, don't redefine), auth dependency from A, consistent error model `{error_code, message, details}`.
- [ ] `/trial/start` is async: return `202` + poll via `/trial/state`, backed by a background worker.

## Tasks — Real Case Acquisition (Mode B, master §10)

- [ ] CourtListener API integration (verify current terms/rate limits before building — record findings in `docs/source_terms.md`).
- [ ] GovInfo as fallback.
- [ ] `insufficient_public_data: true` response path when nothing is found — never fabricate.
- [ ] This can be built and tested independently of the graph work; not blocked on C/D.

## Tasks — n8n (master §25)

- [ ] Scheduled workflow: search public sources → new evidence? → store/process/re-evaluate → Telegram notification.
- [ ] Internal endpoint(s) for n8n → FastAPI calls, separate service-token auth (not user JWT).

## Tasks — Frontend (master §27)

- [ ] Dashboard, Case Creation (upload + public search + synthetic picker), Evidence Explorer, Courtroom (live/replay panels per agent), Evidence Graph (`react-flow`), Trial Replay (timeline), Verdict (with disclaimer banner).
- [ ] React Query/SWR for server state; no business logic duplicated client-side.
- [ ] Build every screen against your own mocked API responses first if needed, then point at your real FastAPI once endpoints are live — you control both sides here so this is the least risky integration point.

## Interfaces you consume (frozen, don't redefine locally)

- All schemas in `INTERFACES.md §3`.
- `ingest_document()` (B), `retrieve()` (B, only if you build any direct-search UI feature), `run_trial`/`resume_trial` (C/D via mock → real).

## Testing

- Endpoint tests against A's fixture case, using the mock graph first, then the real graph at integration checkpoint.
- Frontend: component tests + one full Cypress/Playwright flow (upload → start trial → view verdict) run against the mock graph in CI (fast, deterministic), and manually against the real graph before demo.

## Acceptance criteria (mirrors master §39 Phases 12–16)

- [ ] All endpoints in master §26 implemented with validation + auth
- [ ] All frontend screens functional against the real backend
- [ ] Evidence graph renders the full Claim→Evidence→Source→Document chain on click
- [ ] Trial replay matches true event order
- [ ] n8n workflow detects new evidence and posts a notification on the demo case

## Integration notes

You are the person most exposed to other members' interface drift, so your CI should run against **both** mock and real graph/RAG in separate jobs — if the mock-based tests pass but real-graph tests fail, that's a C/D or B contract violation to flag, not a bug in your code to work around silently.
