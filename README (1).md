# AI Courtroom

A multi-agent AI system that simulates a courtroom trial over a case's evidence: intake structures the case, prosecution and defense agents argue from the evidence, a fact-checker and evidence-quality scorer verify claims, a cross-examination loop stress-tests weak arguments, and a judge agent (with a human-in-the-loop pause point) produces a final verdict.

> **Disclaimer:** This is an educational/research simulation. It is not legal advice and does not represent a real legal decision-maker. Every verdict the system produces carries this disclaimer in its output.

---

## How it works

```
START → INTAKE → EVIDENCE RETRIEVAL → PROSECUTION ‖ DEFENSE
      → FACT CHECK → EVIDENCE QUALITY → CROSS-EXAMINATION (bounded loop)
      → [NEEDS_HUMAN_INPUT?] → JUDGE → END
```

- **Intake** turns raw case text into a structured case (parties, claims, legal questions), flagging unknowns and contradictions instead of guessing.
- **Prosecution / Defense** each retrieve their own evidence per claim and build arguments grounded in `evidence_id`s — an argument with no supporting evidence is emitted as "no evidence found" rather than fabricated.
- **Fact Checker** independently re-verifies every claim (`SUPPORTED` / `CONTRADICTED` / `PARTIALLY_SUPPORTED` / `UNVERIFIED`) using its own retrieval, not just the evidence already cited.
- **Evidence Quality** scores every cited item on reliability, directness, relevance, corroboration, and recency.
- **Cross-Examination** runs a bounded loop (default 3 rounds) that challenges the weakest argument, routes it to the other side, and re-checks it — guaranteed to terminate even if the sides never converge.
- **Judge** consumes the full trial state and produces a verdict under one of three profiles (`strict` / `balanced` / `skeptical`), validating that every cited `evidence_id` actually exists before trusting it.
- **Human-in-the-loop**: if unresolved questions remain, the graph pauses (LangGraph `interrupt()`) and can be resumed later with new evidence — only the claims flagged for reassessment are re-run, not the whole case.

The full contract (Pydantic schemas, the `CourtroomState` graph state, and every cross-team function signature) is frozen in [`INTERFACES.md`](./INTERFACES.md). Each stage was originally scoped as its own build plan — see `PLAN_A_foundation.md` through `PLAN_E_api_frontend.md` for the original phased build breakdown.

## Architecture

| Layer | Tech |
|---|---|
| Agents & orchestration | LangGraph, LangChain-core |
| API | FastAPI, Pydantic v2, JWT auth |
| Database | SQLite (default, file-backed) or Postgres — same schema either way |
| Ingestion | `pypdf`, `python-docx`, paragraph-aware chunking |
| Retrieval / embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`), automatic offline TF-IDF fallback if no internet |
| Frontend | React 18, TypeScript, Vite, Tailwind, TanStack Query, React Flow |
| Automation | n8n (scheduled evidence monitoring → Telegram notification) |

```
backend/app/agents/     → intake, prosecution, defense, fact_checker,
                           evidence_quality, cross_examiner, judge
backend/app/graph/      → CourtroomState, build_graph.py, run.py / run_mock.py
backend/app/rag/        → retrieve.py (real) / retrieve_mock.py, embeddings.py
backend/app/ingestion/  → parsers, chunker, ingest orchestration
backend/app/database/   → migrations, typed DB client
backend/app/api/        → FastAPI routers, services, auth
frontend/               → React app (Dashboard, Courtroom, Evidence Graph, Verdict, Trial Replay)
n8n/                    → evidence-monitoring workflow
```

Every cross-boundary dependency has a mock (`retrieve_mock`, `run_mock`) so any layer can be developed and tested independently of the others, then flipped to the real implementation with a single env var.

## Getting started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> If you're on a machine with limited disk space, `sentence-transformers` (~pulls in `torch`) is the heaviest dependency. The system falls back automatically to an offline TF-IDF retriever if it isn't installed or can't reach the internet — nothing crashes either way.

### 2. Configure environment

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Key flags in `backend/.env` (or root `.env`, whichever your setup reads):

| Variable | Default | What it does |
|---|---|---|
| `USE_MOCK_GRAPH` | `false`* | `true` → hardcoded schema-valid trial state, no agents run. `false` → real LangGraph pipeline. |
| `USE_MOCK_RAG` | `false`* | `true` → returns 2 canned evidence hits. `false` → real embedding-based retrieval. |
| `USE_MOCK_LLM` | `true` | `true` → agents return fixed valid JSON, no API calls, no cost. `false` → real LLM calls (needs `OPENAI_API_KEY`). |
| `DATABASE_URL` | `sqlite:///./courtroom.sqlite3` | Swap for a `postgresql://...` URL for multi-user/production use. |

\* Defaults differ slightly between `.env.example` and `backend/.env.example` — check whichever file you copied. For a first run, mock everything (`USE_MOCK_GRAPH=true`, `USE_MOCK_RAG=true`, `USE_MOCK_LLM=true`) to confirm the full stack works end-to-end before pointing at real retrieval/LLM calls.

### 3. Run the test suite

```bash
pytest
```

### 4. Start the backend

Run this from the **repo root** (not from inside `backend/`):

```bash
uvicorn backend.app.api.main:app --reload
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173 and proxies API calls to the backend on port 8000.

## Typical flow

1. Register / log in.
2. Create a case, either by uploading documents or using the seeded synthetic fixture (`data/demo_cases/case_001/`).
3. Start a trial (`POST /trial/start`) — this runs in the background; poll `GET /trial/state` (the frontend does this automatically every 3s while the trial is `pending`/`running`).
4. If the trial pauses for human input, review the unresolved questions and call `POST /trial/intervene` → `POST /trial/resume`.
5. View the verdict, the evidence graph, and the full trial replay.

## Known limitations

- Real LLM calls are mocked by default — set `OPENAI_API_KEY` and `USE_MOCK_LLM=false` for genuine agent reasoning instead of fixed responses.
- SQLite is fine for a single-instance demo; use Postgres (`DATABASE_URL=postgresql://...`) for concurrent multi-user load.
- The TF-IDF embedding fallback re-fits per query rather than storing a stable vector per chunk, so it's slower than the sentence-transformer path — acceptable for a demo, not for scale.

See [`INTEGRATION_REPORT.md`](./INTEGRATION_REPORT.md) for the full list of issues found and fixed during integration.
