"""
backend/app/api/routers/cases.py
─────────────────────────────────
POST   /cases
GET    /cases
GET    /cases/{case_id}
DELETE /cases/{case_id}
POST   /cases/search-public
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.database import adapter as db
from app.api.dependencies.auth import get_current_user
from app.api.services.search_service import search_public_cases
from app.models.schemas import CaseRow, CreateCaseRequest, PublicSearchRequest

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CreateCaseRequest,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    case = await db.create_case(
        owner_id=current_user["user_id"],
        title=body.title,
        description=body.description,
        provenance_type=body.provenance_type,
    )
    return case


@router.get("", response_model=List[Dict[str, Any]])
async def list_cases(
    current_user: Dict[str, str] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return await db.list_cases(current_user["user_id"])


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    case = await db.get_case(case_id, current_user["user_id"])
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> None:
    deleted = await db.delete_case(case_id, current_user["user_id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")


@router.post("/search-public")
async def search_public(
    body: PublicSearchRequest,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Searches CourtListener (primary) and GovInfo (fallback) for public legal cases.
    Returns insufficient_public_data: true when nothing is found.
    Never fabricates results.
    """
    return await search_public_cases(
        query=body.query,
        jurisdiction=body.jurisdiction,
        date_from=body.date_from,
        date_to=body.date_to,
        top_k=body.top_k,
    )
