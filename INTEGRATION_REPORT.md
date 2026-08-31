# AI Courtroom — Integration & Completion Report

Status after this pass: **158/158 tests passing** (`pytest` from repo root runs
both suites together — see "Running tests" below).

## What was broken, and what was fixed

### Carried over from Codex's partial run (usage limit hit mid-task)
| # | Issue | Fix |
|---|---|---|
| 1 | `main.py`: a namespace-consolidation find/replace accidentally rewrote the local FastAPI `app` variable inside `create_app()` to `backend.app`, breaking every route registration | Restored to local `app.*` calls |
| 2 | `backend/tests/test_contracts.py` imported API-only response models (`TokenResponse`, `EvidenceGraphResponse`, `ReplayResponse`) from the canonical `backend.app.models.schemas` instead of `backend.app.api.schemas` where Codex had moved them | Fixed the import split |
| 3 | `backend/tests/conftest.py` referenced `db_module.settings.sqlite_path`, an attribute that no longer exists after the DB layer was consolidated | Updated to patch `DATABASE_URL`/`SQLITE_PATH` env vars, which the real client reads |
| 4 | `verdicts` table has 11 columns; the `INSERT` supplied only 10 values | Fixed placeholder count |
| 5 | `verdict_evidence` rows referenced `evidence_id`s (often from the mock RAG pool) that don't exist in the case's `evidence` table, violating the foreign key and crashing verdict persistence | `save_verdict` now backfills a minimal evidence placeholder row when needed |
| 6 | Leftover duplicate `backend/app/app/` package tree from the merge | Removed (confirmed nothing referenced it first) |

### Found and fixed during this pass
| # | Issue | Fix |
|---|---|---|
| 7 | **`needs_human_input_node` never called LangGraph's `interrupt()`** — it was a pure passthrough, so the graph silently continued straight to `judge` regardless of unresolved `NEEDS_REVIEW` questions. Human-in-the-loop never actually paused anything. | Now calls `interrupt()` with the unresolved-questions payload; folds the resumed `HumanIntervention` back into state. Covered by `tests/test_human_interrupt.py`. |
| 8 | **`_make_checkpointer()` created a brand-new, empty `MemorySaver()` on every call.** Even after fixing #7, a trial paused by `run_trial()` would be invisible to a later `resume_trial()` call — different checkpointer instance, no memory of the pause. | Now derives a persistent, file-backed `SqliteSaver` from `DATABASE_URL` (Postgres still supported/preferred if `DATABASE_URL` is a `postgresql://` URL); `MemorySaver` is only used as a last resort, with a loud warning that it can't support real pause/resume. |
| 9 | **`_load_case_description` only recognized the hardcoded `case_001` fixture.** Any real case created through `POST /cases` would make `run_trial()` immediately raise `ValueError`. | Now queries the real database first; falls back to the `case_001` synthetic fixture for offline/tests. |
| 10 | `backend/app/rag/retrieve.py`'s real path (`retrieve_real.py`) and all of `backend/app/ingestion/` did not exist — Plan B was entirely unbuilt. | Built both (see below). |
| 11 | Running `pytest tests/ backend/tests/` together (or a bare `pytest` after config was unified) failed one test intermittently, due to an env-var leak: `backend/tests/conftest.py` sets `USE_MOCK_GRAPH=true` at **collection time**, which gets baked into `backend.app.graph.run`'s own imported copy of that constant — invisible to `tests/conftest.py`'s monkeypatching, which only patched `cfg.USE_MOCK_GRAPH`, not `run_mod.USE_MOCK_GRAPH`. | `tests/conftest.py`'s `force_mock_env` fixture now also patches `backend.app.graph.run.USE_MOCK_GRAPH` directly. Verified order-independent (`pytest tests/ backend/tests/` and `pytest backend/tests/ tests/` both pass). |
| 12 | Root `pyproject.toml` only collected `tests/` — running bare `pytest` silently skipped `backend/tests/` entirely. | `testpaths = ["tests", "backend/tests"]`. |

## What was built from scratch (Plan A / Plan B were missing entirely)

### Plan A — Database (`backend/app/database/`)
Already substantially present from Codex's earlier work: `migrations/0001_init.sql`
(reconstructed from `INTERFACES.md §2/§8` plus every table/column implied by
`schemas.py`), a `client.py` with async CRUD for every owned table, and
`data/demo_cases/case_001/` fixtures. Verified end-to-end via live smoke tests
(not just the test suite): real user/case creation, real HTTP requests through
`TestClient` (register → login → create case), all succeeded.

**Inferred/reconstructed schema note:** since the original `IMPLEMENTATION_PLAN.md`
§8 (the true source of the full DDL) is not in this repo, column types/constraints
not explicitly stated anywhere were inferred from the corresponding Pydantic
field types in `schemas.py`. This is a best-effort reconstruction, not a
verbatim recovery — worth a quick review against the original plan if anyone
on the team still has a copy.

### Plan B — Ingestion + real RAG (built this pass, was entirely missing)
- `backend/app/ingestion/parsers.py` — PDF (`pypdf`), DOCX (`python-docx`), TXT extraction.
- `backend/app/ingestion/chunker.py` — paragraph-aware chunking with overlap.
- `backend/app/ingestion/ingest.py` — orchestrates parse → chunk → embed → persist
  chunks + evidence rows. This is the exact function `documents.py` already
  expected (`backend.app.ingestion.ingest.ingest_document`), previously always
  falling back to a no-op stub.
- `backend/app/rag/embeddings.py` — local embedding backend, **no paid/hosted API**:
  - Primary: `sentence-transformers` (`all-MiniLM-L6-v2`, ~80MB, downloads once).
  - Automatic fallback: offline TF-IDF (scikit-learn) if the model can't be
    downloaded (no internet) — verified this actually triggers and works
    correctly in a sandboxed/offline environment during testing.
- `backend/app/rag/retrieve_real.py` — the real `retrieve()` (INTERFACES.md §6
  signature), cosine-similarity ranked over a case's ingested chunks.

**Verified live** (not just unit tests): ingested a real multi-section .txt
document, confirmed real chunks + evidence rows were persisted, and confirmed
different queries correctly re-ranked which chunk scored highest (e.g. a
"prepayment/invoice" query scored the payment-terms chunk higher than an
"export control/delay" query, which correctly favored the witness-statement
chunk).

**Tradeoff to know about:** the TF-IDF fallback path is not stable across
separate calls (see docstring in `embeddings.py`) — it refits over the case's
full chunk corpus + query at *retrieval* time rather than using a precomputed,
stored vector per chunk (which the sentence-transformer path does). This is
slower per query but keeps the system fully functional with zero internet
dependency, which matters for a demo environment.

## Still open / needs a human decision

- **The original `IMPLEMENTATION_PLAN.md`** (with the verbatim §8 DDL) was
  never recovered. If any teammate has the original file, it's worth a diff
  against `backend/app/database/migrations/0001_init.sql` to confirm nothing
  was mis-inferred.
- **Real LLM calls** are still mocked by default (`USE_MOCK_LLM=true`) since
  no API key is configured — set `OPENAI_API_KEY` (or whichever provider
  `llm_client.py` is wired to) and flip `USE_MOCK_LLM=false` to use a real
  model for agent reasoning.
- **Postgres** is supported (`DATABASE_URL=postgresql://...`) but SQLite is
  the default — fine for a demo/single-instance deployment, not for
  concurrent multi-user production load.

## Running this project from zero

```bash
# 1. Install dependencies
pip install -r requirements.txt
# (or: pip install -e . && pip install -e backend/)

# 2. Set up environment
cp .env.example .env
cp backend/.env.example backend/.env
# Edit .env / backend/.env if you want real LLM calls (set OPENAI_API_KEY,
# USE_MOCK_LLM=false) or Postgres (set DATABASE_URL=postgresql://...).
# Defaults work out of the box with SQLite + mocked LLM.

# 3. Run the full test suite (both C/D's graph suite and E's API suite)
pytest
# → 158 passed

# 4. Start the API server
cd backend
uvicorn app.api.main:app --reload
# → http://localhost:8000/docs for interactive API docs
# → http://localhost:8000/health for a quick check

# 5. (Optional) Start the frontend, if Node/npm is available
cd frontend
npm install
npm run dev
```

First real ingestion request will download the `all-MiniLM-L6-v2` embedding
model (~80MB, one-time, needs internet) — if that's not available, the system
automatically falls back to offline TF-IDF embeddings with a logged warning,
no crash.
