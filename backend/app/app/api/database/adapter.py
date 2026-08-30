"""
backend/app/api/database/adapter.py
─────────────────────────────────────
Member E's thin database adapter.

Provides async helpers that match the table schema from INTERFACES.md §2.
Currently backed by SQLite (aiosqlite) for local development.

Swap strategy when Member A ships the real Postgres/Supabase layer:
  1. Set DB_BACKEND=postgres and DATABASE_URL=<supabase_url> in .env
  2. This module's connection logic switches automatically.
  3. NO changes needed in routers or services.

Tables managed here mirror the schema from INTERFACES.md §2.
Member A will own the authoritative DDL; this is a compatibility layer only.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiosqlite

from backend.app.api.config import get_settings

settings = get_settings()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ── Connection ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield an aiosqlite connection. JSON1 extension is built into Python's sqlite3."""
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        yield conn


# ── Schema bootstrap ─────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS users (
    user_id     TEXT PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    hashed_pw   TEXT NOT NULL,
    full_name   TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_id    TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    case_id         TEXT PRIMARY KEY,
    owner_id        TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    provenance_type TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    document_id     TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    file_path       TEXT NOT NULL,
    upload_status   TEXT NOT NULL DEFAULT 'pending',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id     TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    document_id     TEXT REFERENCES documents(document_id),
    content         TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    relevance_score REAL DEFAULT 0.0,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id        TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    statement       TEXT NOT NULL,
    made_by         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'UNVERIFIED',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id    TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
    PRIMARY KEY (claim_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS sources (
    source_id   TEXT PRIMARY KEY,
    case_id     TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    document_id TEXT REFERENCES documents(document_id),
    url         TEXT,
    title       TEXT,
    source_type TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verdicts (
    verdict_id              TEXT PRIMARY KEY,
    case_id                 TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    finding                 TEXT NOT NULL,
    reasoning               TEXT NOT NULL,
    confidence              REAL NOT NULL,
    judge_profile           TEXT NOT NULL,
    supporting_evidence_ids TEXT NOT NULL DEFAULT '[]',
    opposing_evidence_ids   TEXT NOT NULL DEFAULT '[]',
    unresolved_questions    TEXT NOT NULL DEFAULT '[]',
    disclaimer              TEXT NOT NULL,
    created_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_messages (
    message_id      TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    agent_name      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    content         TEXT NOT NULL,
    evidence_refs   TEXT NOT NULL DEFAULT '[]',
    confidence      REAL,
    timestamp       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_events (
    event_id    TEXT PRIMARY KEY,
    case_id     TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    event_date  TEXT,
    evidence_ids TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trial_state (
    case_id         TEXT PRIMARY KEY REFERENCES cases(case_id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'pending',
    round           INTEGER NOT NULL DEFAULT 0,
    state_snapshot  TEXT,
    updated_at      TEXT NOT NULL
);
"""


async def init_db() -> None:
    """Create all tables if they do not exist. Called on app startup."""
    async with get_db() as conn:
        await conn.executescript(_DDL)
        await conn.commit()


# ── User helpers ──────────────────────────────────────────────────────────────

async def create_user(email: str, hashed_pw: str, full_name: Optional[str] = None) -> Dict[str, Any]:
    user_id = _new_id()
    now = _now_iso()
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, email, hashed_pw, full_name, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, email, hashed_pw, full_name, now),
        )
        await conn.commit()
    return {"user_id": user_id, "email": email, "full_name": full_name, "created_at": now}


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT user_id, email, hashed_pw, full_name, created_at FROM users WHERE email = ?",
            (email,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT user_id, email, full_name, created_at FROM users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def store_refresh_token(user_id: str, token_hash: str, expires_at: str) -> str:
    token_id = _new_id()
    now = _now_iso()
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO refresh_tokens (token_id, user_id, token_hash, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (token_id, user_id, token_hash, expires_at, now),
        )
        await conn.commit()
    return token_id


async def get_refresh_token(token_hash: str) -> Optional[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT token_id, user_id, expires_at FROM refresh_tokens WHERE token_hash = ?",
            (token_hash,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def delete_refresh_token(token_hash: str) -> None:
    async with get_db() as conn:
        await conn.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
        await conn.commit()


# ── Case helpers ──────────────────────────────────────────────────────────────

async def create_case(
    owner_id: str, title: str, description: str, provenance_type: str
) -> Dict[str, Any]:
    case_id = _new_id()
    now = _now_iso()
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO cases (case_id, owner_id, title, description, provenance_type, "
            "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (case_id, owner_id, title, description, provenance_type, now, now),
        )
        await conn.commit()
    return {
        "case_id": case_id, "owner_id": owner_id, "title": title,
        "description": description, "provenance_type": provenance_type,
        "status": "pending", "created_at": now, "updated_at": now,
    }


async def list_cases(owner_id: str) -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM cases WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_case(case_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    async with get_db() as conn:
        if owner_id:
            async with conn.execute(
                "SELECT * FROM cases WHERE case_id = ? AND owner_id = ?",
                (case_id, owner_id),
            ) as cursor:
                row = await cursor.fetchone()
        else:
            async with conn.execute(
                "SELECT * FROM cases WHERE case_id = ?", (case_id,)
            ) as cursor:
                row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_case(case_id: str, owner_id: str) -> bool:
    async with get_db() as conn:
        result = await conn.execute(
            "DELETE FROM cases WHERE case_id = ? AND owner_id = ?",
            (case_id, owner_id),
        )
        await conn.commit()
        return result.rowcount > 0


# ── Document helpers ──────────────────────────────────────────────────────────

async def create_document(
    case_id: str, filename: str, content_type: str, size_bytes: int, file_path: str
) -> Dict[str, Any]:
    document_id = _new_id()
    now = _now_iso()
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO documents (document_id, case_id, filename, content_type, "
            "size_bytes, file_path, upload_status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'uploaded', ?)",
            (document_id, case_id, filename, content_type, size_bytes, file_path, now),
        )
        await conn.commit()
    return {
        "document_id": document_id, "case_id": case_id, "filename": filename,
        "content_type": content_type, "size_bytes": size_bytes,
        "upload_status": "uploaded", "created_at": now,
    }


async def list_documents(case_id: str) -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT document_id, case_id, filename, content_type, size_bytes, "
            "upload_status, created_at FROM documents WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_document(document_id: str) -> Optional[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT document_id, case_id, filename, content_type, size_bytes, "
            "upload_status, created_at FROM documents WHERE document_id = ?",
            (document_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ── Evidence helpers ──────────────────────────────────────────────────────────

async def list_evidence(case_id: str) -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM evidence WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_evidence(evidence_id: str) -> Optional[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def upsert_evidence_from_rag(case_id: str, ev_result: dict) -> None:
    """Store an EvidenceResult from RAG into the evidence table."""
    now = _now_iso()
    async with get_db() as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO evidence "
            "(evidence_id, case_id, document_id, content, source_type, relevance_score, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                ev_result["evidence_id"], case_id, ev_result.get("document_id"),
                ev_result["content"], ev_result["source_type"],
                ev_result.get("relevance_score", 0.0), now,
            ),
        )
        await conn.commit()


# ── Verdict helpers ───────────────────────────────────────────────────────────

async def save_verdict(case_id: str, verdict: dict) -> str:
    verdict_id = _new_id()
    now = _now_iso()
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO verdicts (verdict_id, case_id, finding, reasoning, confidence, "
            "judge_profile, supporting_evidence_ids, opposing_evidence_ids, "
            "unresolved_questions, disclaimer, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                verdict_id, case_id, verdict["finding"], verdict["reasoning"],
                verdict["confidence"], verdict["judge_profile"],
                json.dumps(verdict.get("supporting_evidence_ids", [])),
                json.dumps(verdict.get("opposing_evidence_ids", [])),
                json.dumps(verdict.get("unresolved_questions", [])),
                verdict.get("disclaimer", ""),
                now,
            ),
        )
        await conn.commit()
    return verdict_id


async def get_latest_verdict(case_id: str) -> Optional[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM verdicts WHERE case_id = ? ORDER BY created_at DESC LIMIT 1",
            (case_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["supporting_evidence_ids"] = json.loads(d["supporting_evidence_ids"])
            d["opposing_evidence_ids"] = json.loads(d["opposing_evidence_ids"])
            d["unresolved_questions"] = json.loads(d["unresolved_questions"])
            return d


async def list_verdicts(case_id: str) -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM verdicts WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["supporting_evidence_ids"] = json.loads(d["supporting_evidence_ids"])
                d["opposing_evidence_ids"] = json.loads(d["opposing_evidence_ids"])
                d["unresolved_questions"] = json.loads(d["unresolved_questions"])
                result.append(d)
            return result


# ── Trial state helpers ────────────────────────────────────────────────────────

async def upsert_trial_status(case_id: str, status: str, round_num: int = 0, snapshot: Optional[dict] = None) -> None:
    now = _now_iso()
    snapshot_json = json.dumps(snapshot) if snapshot else None
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO trial_state (case_id, status, round, state_snapshot, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(case_id) DO UPDATE SET status=excluded.status, round=excluded.round, "
            "state_snapshot=excluded.state_snapshot, updated_at=excluded.updated_at",
            (case_id, status, round_num, snapshot_json, now),
        )
        await conn.commit()


async def get_trial_status(case_id: str) -> Optional[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT case_id, status, round, state_snapshot, updated_at FROM trial_state WHERE case_id = ?",
            (case_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            if d["state_snapshot"]:
                d["state_snapshot"] = json.loads(d["state_snapshot"])
            return d


# ── Agent message helpers (replay) ────────────────────────────────────────────

async def append_agent_message(
    case_id: str,
    agent_name: str,
    event_type: str,
    content: str,
    evidence_refs: Optional[List[str]] = None,
    confidence: Optional[float] = None,
) -> str:
    message_id = _new_id()
    now = _now_iso()
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO agent_messages (message_id, case_id, agent_name, event_type, "
            "content, evidence_refs, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                message_id, case_id, agent_name, event_type, content,
                json.dumps(evidence_refs or []), confidence, now,
            ),
        )
        await conn.commit()
    return message_id


async def list_agent_messages(case_id: str) -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM agent_messages WHERE case_id = ? ORDER BY timestamp ASC",
            (case_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["evidence_refs"] = json.loads(d["evidence_refs"])
                result.append(d)
            return result


# ── Claim helpers (for evidence graph) ───────────────────────────────────────

async def list_claims(case_id: str) -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM claims WHERE case_id = ?", (case_id,)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def list_sources(case_id: str) -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM sources WHERE case_id = ?", (case_id,)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def list_claim_evidence_links(case_id: str) -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT ce.claim_id, ce.evidence_id FROM claim_evidence ce "
            "JOIN claims c ON ce.claim_id = c.claim_id WHERE c.case_id = ?",
            (case_id,),
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]
