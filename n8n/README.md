# n8n Automation Workflows (Member E)

This directory contains optional n8n automation workflows for the AI Courtroom project.

## Architecture

```
n8n (Scheduled / Webhook)
       │
       ▼ [X-Service-Token Header]
FastAPI internal endpoint (/internal/...)
       │
       ▼
Shared Application Services
       │
       ▼
RAG / Graph / Database
```

> **Security Rule:** n8n NEVER communicates directly with the database or LangGraph internals. It communicates exclusively via FastAPI internal endpoints using a dedicated `X-Service-Token` (not user JWTs).

## Workflows Included

### 1. Evidence Monitor (`workflows/evidence_monitor.json`)
- **Trigger**: Cron schedule (e.g. hourly or daily).
- **Step 1**: Queries FastAPI `/internal/health` to verify service readiness.
- **Step 2**: Queries CourtListener/GovInfo or public legal feeds for new precedents or filings matching active case topics.
- **Step 3**: If new relevant documents are detected, calls `POST /internal/cases/{case_id}/notify-new-evidence` with the findings.
- **Step 4**: Sends an alert notification (Telegram/Webhook).

## How to Import

1. Open your n8n web interface (e.g. `http://localhost:5678`).
2. Go to **Workflows** → **Import from File**.
3. Select `n8n/workflows/evidence_monitor.json`.
4. Configure the environment variables/credentials in n8n:
   - `API_BASE_URL`: `http://localhost:8000`
   - `SERVICE_TOKEN`: Matches `N8N_SERVICE_TOKEN` in `backend/.env`.
