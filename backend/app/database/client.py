"""SQLite persistence client for the assembled AI Courtroom application.

The client intentionally exposes small async helpers rather than allowing API,
ingestion, or graph code to issue ad-hoc SQL.  SQLite stores embedding vectors
as JSON; the real retriever performs cosine ranking in-process.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import aiosqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return str(uuid.uuid4())


def database_path() -> Path:
    """Resolve DATABASE_URL/SQLITE_PATH without requiring the API package."""
    url = os.getenv("DATABASE_URL", "sqlite:///./courtroom.sqlite3")
    if not url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// DATABASE_URL values are supported by the local store")
    raw_path = url.removeprefix("sqlite:///") or os.getenv("SQLITE_PATH", "courtroom.sqlite3")
    return Path(raw_path).expanduser()


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA journal_mode = WAL")
        yield conn


async def init_db() -> None:
    migration = Path(__file__).parent / "migrations" / "0001_init.sql"
    async with get_db() as conn:
        await conn.executescript(migration.read_text(encoding="utf-8"))
        await conn.commit()


def _row(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _decode_json_fields(data: dict[str, Any], *fields: str) -> dict[str, Any]:
    for field in fields:
        if isinstance(data.get(field), str):
            data[field] = json.loads(data[field])
    return data


async def create_user(email: str, hashed_pw: str, full_name: str | None = None) -> dict[str, Any]:
    user_id, now = _id(), _now()
    async with get_db() as conn:
        await conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (user_id, email, hashed_pw, full_name, now))
        await conn.commit()
    return {"user_id": user_id, "email": email, "full_name": full_name, "created_at": now}


async def get_user_by_email(email: str) -> dict[str, Any] | None:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM users WHERE email = ?", (email,)) as cur:
            return _row(await cur.fetchone())


async def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return _row(await cur.fetchone())


async def store_refresh_token(user_id: str, token_hash: str, expires_at: str) -> str:
    token_id, now = _id(), _now()
    async with get_db() as conn:
        await conn.execute("INSERT INTO refresh_tokens VALUES (?, ?, ?, ?, ?)", (token_id, user_id, token_hash, expires_at, now))
        await conn.commit()
    return token_id


async def get_refresh_token(token_hash: str) -> dict[str, Any] | None:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM refresh_tokens WHERE token_hash = ?", (token_hash,)) as cur:
            return _row(await cur.fetchone())


async def delete_refresh_token(token_hash: str) -> None:
    async with get_db() as conn:
        await conn.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
        await conn.commit()


async def create_case(owner_id: str, title: str, description: str, provenance_type: str) -> dict[str, Any]:
    case_id, now = _id(), _now()
    async with get_db() as conn:
        await conn.execute("INSERT INTO cases VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)", (case_id, owner_id, title, description, provenance_type, now, now))
        await conn.commit()
    return {"case_id": case_id, "owner_id": owner_id, "title": title, "description": description, "provenance_type": provenance_type, "status": "pending", "created_at": now, "updated_at": now}


async def list_cases(owner_id: str) -> list[dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM cases WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def get_case(case_id: str, owner_id: str | None = None) -> dict[str, Any] | None:
    query, args = ("SELECT * FROM cases WHERE case_id = ?", (case_id,)) if owner_id is None else ("SELECT * FROM cases WHERE case_id = ? AND owner_id = ?", (case_id, owner_id))
    async with get_db() as conn:
        async with conn.execute(query, args) as cur:
            return _row(await cur.fetchone())


async def delete_case(case_id: str, owner_id: str) -> bool:
    async with get_db() as conn:
        cur = await conn.execute("DELETE FROM cases WHERE case_id = ? AND owner_id = ?", (case_id, owner_id))
        await conn.commit()
        return cur.rowcount > 0


async def create_document(case_id: str, filename: str, content_type: str, size_bytes: int, file_path: str) -> dict[str, Any]:
    document_id, now = _id(), _now()
    async with get_db() as conn:
        await conn.execute("INSERT INTO documents (document_id, case_id, filename, content_type, size_bytes, file_path, upload_status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'uploaded', ?)", (document_id, case_id, filename, content_type, size_bytes, file_path, now))
        await conn.commit()
    return {"document_id": document_id, "case_id": case_id, "filename": filename, "content_type": content_type, "size_bytes": size_bytes, "file_path": file_path, "upload_status": "uploaded", "created_at": now}


async def update_document_ingestion(document_id: str, *, content_hash: str, extracted_text: str, document_type: str, status: str) -> None:
    async with get_db() as conn:
        await conn.execute("UPDATE documents SET content_hash=?, extracted_text=?, document_type=?, upload_status=? WHERE document_id=?", (content_hash, extracted_text, document_type, status, document_id))
        await conn.commit()


async def list_documents(case_id: str) -> list[dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM documents WHERE case_id = ? ORDER BY created_at", (case_id,)) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def get_document(document_id: str) -> dict[str, Any] | None:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,)) as cur:
            return _row(await cur.fetchone())


async def insert_chunk(document_id: str, case_id: str, chunk_index: int, content: str, embedding: list[float], page_number: int | None = None) -> str:
    chunk_id, now = _id(), _now()
    async with get_db() as conn:
        await conn.execute("INSERT INTO document_chunks (chunk_id, document_id, case_id, chunk_index, content, embedding, page_number, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (chunk_id, document_id, case_id, chunk_index, content, json.dumps(embedding), page_number, now))
        await conn.commit()
    return chunk_id


async def list_chunks(case_id: str) -> list[dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM document_chunks WHERE case_id = ? ORDER BY document_id, chunk_index", (case_id,)) as cur:
            return [_decode_json_fields(dict(row), "embedding") for row in await cur.fetchall()]


async def upsert_evidence_from_rag(case_id: str, ev_result: dict[str, Any]) -> None:
    now = _now()
    async with get_db() as conn:
        await conn.execute("INSERT INTO evidence (evidence_id, case_id, document_id, content, source_type, relevance_score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(evidence_id) DO UPDATE SET content=excluded.content, relevance_score=excluded.relevance_score", (ev_result["evidence_id"], case_id, ev_result.get("document_id"), ev_result["content"], ev_result["source_type"], ev_result.get("relevance_score", 0.0), now))
        await conn.commit()


async def create_evidence(case_id: str, document_id: str, chunk_id: str, content: str, source_type: str, relevance_score: float = 0.0) -> str:
    evidence_id, now = _id(), _now()
    async with get_db() as conn:
        await conn.execute("INSERT INTO evidence (evidence_id, case_id, document_id, chunk_id, content, source_type, relevance_score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (evidence_id, case_id, document_id, chunk_id, content, source_type, relevance_score, now))
        await conn.commit()
    return evidence_id


async def list_evidence(case_id: str) -> list[dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM evidence WHERE case_id = ? ORDER BY created_at", (case_id,)) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def get_evidence(evidence_id: str) -> dict[str, Any] | None:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)) as cur:
            return _row(await cur.fetchone())


async def save_verdict(case_id: str, verdict: dict[str, Any]) -> str:
    verdict_id, now = _id(), _now()
    fields = (json.dumps(verdict.get("supporting_evidence_ids", [])), json.dumps(verdict.get("opposing_evidence_ids", [])), json.dumps(verdict.get("unresolved_questions", [])))
    async with get_db() as conn:
        await conn.execute("INSERT INTO verdicts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (verdict_id, case_id, verdict["finding"], verdict["reasoning"], verdict["confidence"], verdict["judge_profile"], *fields, verdict["disclaimer"], now))
        for relation, ids in (("supporting", verdict.get("supporting_evidence_ids", [])), ("opposing", verdict.get("opposing_evidence_ids", []))):
            for evidence_id in ids:
                await conn.execute("INSERT OR IGNORE INTO verdict_evidence VALUES (?, ?, ?)", (verdict_id, evidence_id, relation))
        await conn.commit()
    return verdict_id


async def get_latest_verdict(case_id: str) -> dict[str, Any] | None:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM verdicts WHERE case_id = ? ORDER BY created_at DESC LIMIT 1", (case_id,)) as cur:
            row = _row(await cur.fetchone())
            return _decode_json_fields(row, "supporting_evidence_ids", "opposing_evidence_ids", "unresolved_questions") if row else None


async def list_verdicts(case_id: str) -> list[dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM verdicts WHERE case_id = ? ORDER BY created_at DESC", (case_id,)) as cur:
            return [_decode_json_fields(dict(row), "supporting_evidence_ids", "opposing_evidence_ids", "unresolved_questions") for row in await cur.fetchall()]


async def upsert_trial_status(case_id: str, status: str, round_num: int = 0, snapshot: dict[str, Any] | None = None) -> None:
    async with get_db() as conn:
        await conn.execute("INSERT INTO trial_state VALUES (?, ?, ?, ?, ?) ON CONFLICT(case_id) DO UPDATE SET status=excluded.status, round=excluded.round, state_snapshot=COALESCE(excluded.state_snapshot, trial_state.state_snapshot), updated_at=excluded.updated_at", (case_id, status, round_num, json.dumps(snapshot) if snapshot is not None else None, _now()))
        await conn.execute("UPDATE cases SET status=?, updated_at=? WHERE case_id=?", (status, _now(), case_id))
        await conn.commit()


async def get_trial_status(case_id: str) -> dict[str, Any] | None:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM trial_state WHERE case_id = ?", (case_id,)) as cur:
            row = _row(await cur.fetchone())
            return _decode_json_fields(row, "state_snapshot") if row and row.get("state_snapshot") else row


async def append_agent_message(case_id: str, agent_name: str, event_type: str, content: str, evidence_refs: list[str] | None = None, confidence: float | None = None) -> str:
    message_id = _id()
    async with get_db() as conn:
        await conn.execute("INSERT INTO agent_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (message_id, case_id, agent_name, event_type, content, json.dumps(evidence_refs or []), confidence, _now()))
        await conn.commit()
    return message_id


async def list_agent_messages(case_id: str) -> list[dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM agent_messages WHERE case_id = ? ORDER BY timestamp, message_id", (case_id,)) as cur:
            return [_decode_json_fields(dict(row), "evidence_refs") for row in await cur.fetchall()]


async def append_case_event(case_id: str, description: str, event_date: str | None = None, evidence_ids: list[str] | None = None) -> str:
    event_id = _id()
    async with get_db() as conn:
        await conn.execute("INSERT INTO case_events VALUES (?, ?, ?, ?, ?, ?)", (event_id, case_id, description, event_date, json.dumps(evidence_ids or []), _now()))
        await conn.commit()
    return event_id


async def list_claims(case_id: str) -> list[dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM claims WHERE case_id = ?", (case_id,)) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def list_sources(case_id: str) -> list[dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM sources WHERE case_id = ?", (case_id,)) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def list_claim_evidence_links(case_id: str) -> list[dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT ce.claim_id, ce.evidence_id FROM claim_evidence ce JOIN claims c ON c.claim_id=ce.claim_id WHERE c.case_id=?", (case_id,)) as cur:
            return [dict(row) for row in await cur.fetchall()]
