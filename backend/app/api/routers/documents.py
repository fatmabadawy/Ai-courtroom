"""
backend/app/api/routers/documents.py
──────────────────────────────────────
POST /cases/{case_id}/documents   — upload a document
GET  /cases/{case_id}/documents   — list documents for a case
GET  /documents/{document_id}     — get document metadata

Calls Member B's ingest_document() when available.
Falls back to a stub that records the document row only.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.app.api.config import get_settings
from backend.app.api.database import adapter as db
from backend.app.api.dependencies.auth import get_current_user

settings = get_settings()
router = APIRouter(tags=["documents"])

# Allowed MIME types
ALLOWED_TYPES = {
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
}


def _get_ingest_fn():
    """
    Return Member B's ingest_document function when available,
    otherwise return the local stub.
    """
    try:
        from backend.app.ingestion.ingest import ingest_document  # Member B's real module
        return ingest_document
    except ImportError:
        return _stub_ingest


async def _stub_ingest(document_id: str, case_id: str, file_path: str) -> None:
    """
    Stub ingestion used before Member B ships the real implementation.
    Just marks the document as 'uploaded'. Real ingestion will populate
    the chunks/evidence tables.
    """
    pass  # Document row already written by create_document(); nothing more to do yet.


@router.post("/cases/{case_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    current_user: Dict[str, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    # Verify case ownership
    case = await db.get_case(case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{content_type}' is not supported.",
        )

    # Read and validate size
    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size_mb} MB limit.",
        )

    # Save file to disk
    upload_dir = Path(settings.upload_dir) / case_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = Path(file.filename or "upload").name  # strip path traversal
    file_path = upload_dir / safe_filename

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_bytes)

    # Record in DB
    doc_row = await db.create_document(
        case_id=case_id,
        filename=safe_filename,
        content_type=content_type,
        size_bytes=len(file_bytes),
        file_path=str(file_path),
    )

    # Call Member B's ingestion (or stub)
    ingest_fn = _get_ingest_fn()
    await ingest_fn(doc_row["document_id"], case_id, str(file_path))

    return doc_row


@router.get("/cases/{case_id}/documents", response_model=List[Dict[str, Any]])
async def list_documents(
    case_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    case = await db.get_case(case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return await db.list_documents(case_id)


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    doc = await db.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    # Verify caller owns the parent case
    case = await db.get_case(doc["case_id"], current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return doc
