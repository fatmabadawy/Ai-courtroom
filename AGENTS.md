# AGENTS.md — Integration & Architecture Guide (Member E)

This document provides the definitive architectural map, ownership boundaries, mock switching guides, and integration runbooks for **Member E** (FastAPI API, React Frontend & n8n Automation) in the AI Courtroom project.

---

## 1. Ownership Boundaries & Protected Directories

| Directory / File | Owner | Member E Access | Description |
|---|---|---|---|
| `backend/app/api/` | **Member E** | Full Ownership | FastAPI routers, dependencies, DB adapter, search adapters, services |
| `frontend/` | **Member E** | Full Ownership | React 18, Vite, Tailwind, React Flow, TanStack Query |
| `n8n/` | **Member E** | Full Ownership | Automated workflows & service-token integration |
| `backend/app/models/schemas.py` | **Joint (Frozen)** | Read / Strict Conformity | Core Pydantic models from `INTERFACES.md §3` |
| `backend/app/graph/state.py` | **Member C** | Read-Only | `CourtroomState` TypedDict from `INTERFACES.md §4` |
| `backend/app/graph/build_graph.py` | **Members C & D** | **DO NOT TOUCH** | Core LangGraph graph construction |
| `backend/app/database/` | **Member A** | Consumer | Supabase client, migrations, DDL |
| `backend/app/ingestion/` & `backend/app/rag/` | **Member B** | Consumer | Document parsing, chunking, pgvector RAG |
| `backend/app/agents/` | **Members C & D** | Consumer | Agent node implementations |

---

## 2. Integration Modes & Mock Switches

Member E's API layer connects to the rest of the team through **configuration switches** in `backend/.env`.

### Current Development Mode (Mock Mode)
```env
USE_MOCK_GRAPH=true
USE_MOCK_RAG=true
DB_BACKEND=sqlite
SQLITE_PATH=./courtroom_dev.db
```
- **Graph**: Calls `app.graph.run_mock.run_trial()` and `resume_trial()` returning schema-valid fake states.
- **RAG**: Calls `app.rag.retrieve_mock.retrieve()` returning typed `EvidenceResult` objects.
- **Database**: Uses `app.api.database.adapter.py` over local SQLite.
- **Auth**: Uses `app.api.dependencies.auth_mock.py` over PBKDF2/JWT.

### Integration Mode (When Members A/B/C/D Deliver)
To switch to real implementations, **zero router or frontend code changes are needed**. Only update `.env`:

```env
USE_MOCK_GRAPH=false
USE_MOCK_RAG=false
DB_BACKEND=postgres
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<supabase-host>:5432/<db>
```

#### How Each Dependency Plugs In:
1. **Member A (Database & Auth)**:
   - Point `DATABASE_URL` to Member A's Supabase instance.
   - In `backend/app/api/dependencies/auth.py`, change the import from `auth_mock` to `from app.database.auth import decode_access_token`.
2. **Member B (Ingestion & RAG)**:
   - When `USE_MOCK_RAG=false`, `app/api/services/trial_service.py` automatically uses `app/rag/retrieve.py`.
   - `app/api/routers/documents.py` dynamically imports `app.ingestion.ingest.ingest_document`.
3. **Members C & D (LangGraph & Agents)**:
   - When `USE_MOCK_GRAPH=false`, `app/api/services/trial_service.py` imports `app/graph/run.py` instead of `app/graph/run_mock.py`.

---

## 3. How to Run & Verify

### Backend
```powershell
# In backend directory
cd backend

# Create & activate venv
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Start FastAPI development server
uvicorn app.api.main:app --reload --port 8000
```
- Interactive API Swagger docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Frontend
```powershell
# In frontend directory
cd frontend

# Install packages
npm.cmd install

# Start Vite dev server
npm.cmd run dev
```
- UI running at: `http://localhost:5173`

---

## 4. Team Integration Contracts Summary

### `POST /trial/start`
- Returns **HTTP 202 Accepted** immediately.
- Dispatches trial run asynchronously in the background.
- Frontend polls `GET /trial/state?case_id={id}` for status transitions: `pending` → `running` → `completed` (or `paused` if intervention requested).

### Evidence Graph (`GET /cases/{case_id}/evidence-graph`)
- Computes node/edge topology server-side (`Claim` → `Evidence` → `Source` → `Document`).
- Frontend visualizes the topology using `react-flow` with interactive panning/zoom.

### Replay Timeline (`GET /cases/{case_id}/replay`)
- Reads actual chronological sequence of `agent_messages` from the database.
- Renders debate progression across all 7 courtroom agents.
