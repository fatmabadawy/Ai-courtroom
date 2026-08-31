<div align="center">

# ⚖️ AI Courtroom

**A multi-agent AI system that simulates a courtroom trial over your evidence.**

Intake structures the case → Prosecution & Defense argue it → Fact-Checking and Cross-Examination stress-test it → a Judge agent delivers a verdict — with a human able to step in at any point.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agent%20orchestration-1C3C3C)](https://www.langchain.com/langgraph)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Tests](https://img.shields.io/badge/tests-158%20passing-brightgreen)](#3-run-the-test-suite)
[![License](https://img.shields.io/badge/license-educational%2Fresearch-lightgrey)](#️-known-limitations)

</div>

---

> ### ⚠️ Disclaimer
> This is an **educational/research simulation**. It is not legal advice and does not represent a real legal decision-maker. Every verdict the system produces carries this disclaimer in its own output.

---

## 📖 Table of contents

- [How it works](#-how-it-works)
- [Architecture](#️-architecture)
- [Getting started](#-getting-started)
- [Typical flow](#-typical-flow)
- [Known limitations](#️-known-limitations)

---

## 🧠 How it works

```
 START
   │
   ▼
 📋 INTAKE ─────────────── structures raw case text into parties, claims & legal questions
   │
   ▼
 🔎 EVIDENCE RETRIEVAL ──── pulls the relevant evidence for each claim
   │
   ▼
 ⚔️ PROSECUTION ‖ DEFENSE ─ both argue from evidence, in parallel
   │
   ▼
 ✅ FACT CHECK ──────────── independently re-verifies every claim
   │
   ▼
 📊 EVIDENCE QUALITY ────── scores every cited item's reliability & relevance
   │
   ▼
 🔁 CROSS-EXAMINATION ───── bounded challenge loop (max 3 rounds, always terminates)
   │
   ▼
 🙋 NEEDS HUMAN INPUT? ──── pauses here if unresolved questions remain
   │
   ▼
 🧑‍⚖️ JUDGE ────────────────── delivers a verdict (strict / balanced / skeptical)
   │
   ▼
  END
```

| Stage | What it guards against |
|---|---|
| 📋 **Intake** | Guessing — unknowns and contradictions are flagged, not filled in |
| ⚔️ **Prosecution / Defense** | Fabrication — no supporting evidence means an explicit "no evidence found," never an invented argument |
| ✅ **Fact Checker** | Rubber-stamping — re-verifies claims with its own fresh retrieval, not just what was already cited |
| 📊 **Evidence Quality** | Blind trust — every score carries a "system heuristics, not legal standards" disclaimer |
| 🔁 **Cross-Examination** | Infinite disagreement — hard-terminates at `MAX_ROUNDS` even if the two sides never converge |
| 🧑‍⚖️ **Judge** | Hallucinated citations — every `evidence_id` in the verdict is validated against real retrieved evidence before being trusted |

The full contract — every Pydantic schema, the `CourtroomState` graph state, and every cross-team function signature — is frozen in [`INTERFACES.md`](./INTERFACES.md). The original phased build plan for each stage lives in `PLAN_A_foundation.md` → `PLAN_E_api_frontend.md`.

---

## 🏗️ Architecture

| Layer | Tech |
|---|---|
| 🤖 Agents & orchestration | LangGraph, LangChain-core |
| 🚀 API | FastAPI, Pydantic v2, JWT auth |
| 🗄️ Database | SQLite (default) or Postgres — same schema either way |
| 📄 Ingestion | `pypdf`, `python-docx`, paragraph-aware chunking |
| 🔍 Retrieval / embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`), automatic offline TF-IDF fallback |
| 💻 Frontend | React 18, TypeScript, Vite, Tailwind, TanStack Query, React Flow |
| 🔗 Automation | n8n (scheduled evidence monitoring → Telegram notification) |

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

> 💡 Every cross-boundary dependency has a mock (`retrieve_mock`, `run_mock`) so any layer can be built and tested independently, then flipped to the real implementation with a single env var — zero code changes required.

---

## 🚀 Getting started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> 💾 Low on disk space? `sentence-transformers` (pulls in `torch`) is the heaviest dependency. The system falls back automatically to an offline TF-IDF retriever if it isn't installed or can't reach the internet — nothing crashes either way.

### 2. Configure environment

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

| Variable | Default | What it does |
|---|---|---|
| `USE_MOCK_GRAPH` | `false`\* | `true` → hardcoded schema-valid trial state, no agents run. `false` → real LangGraph pipeline. |
| `USE_MOCK_RAG` | `false`\* | `true` → returns 2 canned evidence hits. `false` → real embedding-based retrieval. |
| `USE_MOCK_LLM` | `true` | `true` → agents return fixed valid JSON, no API calls, no cost. `false` → real LLM calls (needs `OPENAI_API_KEY`). |
| `DATABASE_URL` | `sqlite:///./courtroom.sqlite3` | Swap for a `postgresql://...` URL for multi-user/production use. |

\* Defaults differ slightly between the root `.env.example` and `backend/.env.example` — check whichever file you copied. For a first run, mock everything (`USE_MOCK_GRAPH=true`, `USE_MOCK_RAG=true`, `USE_MOCK_LLM=true`) to confirm the full stack works end-to-end before pointing at real retrieval/LLM calls.

### 3. Run the test suite

```bash
pytest
```
```
158 passed ✅
```

### 4. Start the backend

Run from the **repo root** (not from inside `backend/`):

```bash
uvicorn backend.app.api.main:app --reload
```

- 📚 API docs → http://localhost:8000/docs
- ❤️ Health check → http://localhost:8000/health

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

🌐 Frontend runs at http://localhost:5173 and proxies API calls to the backend on port 8000.

---

## 🎬 Typical flow

1. 🔐 Register / log in.
2. 📁 Create a case — upload documents, or use the seeded synthetic fixture (`data/demo_cases/case_001/`).
3. ▶️ Start a trial (`POST /trial/start`) — runs in the background; the frontend polls `GET /trial/state` every 3s while it's `pending`/`running`.
4. 🙋 If the trial pauses for human input, review the unresolved questions, then `POST /trial/intervene` → `POST /trial/resume`.
5. 🏁 View the verdict, the evidence graph, and the full trial replay.

---

## ⚠️ Known limitations

- Real LLM calls are mocked by default — set `OPENAI_API_KEY` and `USE_MOCK_LLM=false` for genuine agent reasoning instead of fixed responses.
- SQLite is fine for a single-instance demo; use Postgres (`DATABASE_URL=postgresql://...`) for concurrent multi-user load.
- The TF-IDF embedding fallback re-fits per query rather than storing a stable vector per chunk, so it's slower than the sentence-transformer path — acceptable for a demo, not for scale.

📄 See [`INTEGRATION_REPORT.md`](./INTEGRATION_REPORT.md) for the full list of issues found and fixed during integration.

<div align="center">

---

Made with ⚖️ + 🤖 as an educational research project.

</div>
