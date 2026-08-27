"""
backend/app/api/services/search_service.py
────────────────────────────────────────────
Adapter for public legal case search: CourtListener + GovInfo fallback.
Verify current terms/rate limits before enabling — see docs/source_terms.md.

Returns `insufficient_public_data: True` when no usable data is found.
NEVER fabricates results.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from app.api.config import get_settings

settings = get_settings()

COURTLISTENER_BASE = "https://www.courtlistener.com/api/rest/v4"
GOVINFO_BASE = "https://api.govinfo.gov"


async def search_public_cases(
    query: str,
    jurisdiction: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Try CourtListener first, fall back to GovInfo.
    Returns dict with 'results' list or 'insufficient_public_data': True.
    """
    # Try CourtListener
    cl_results = await _search_courtlistener(query, jurisdiction, date_from, date_to, top_k)
    if cl_results is not None:
        return {"source": "courtlistener", "results": cl_results}

    # Fall back to GovInfo
    gi_results = await _search_govinfo(query, top_k)
    if gi_results is not None:
        return {"source": "govinfo", "results": gi_results}

    return {"insufficient_public_data": True, "results": []}


async def _search_courtlistener(
    query: str,
    jurisdiction: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    top_k: int,
) -> Optional[List[Dict[str, Any]]]:
    """Query CourtListener RECAP search API. Returns None on any error."""
    if not settings.courtlistener_api_key:
        return None  # No key configured — skip

    params: Dict[str, Any] = {
        "q": query,
        "type": "o",  # opinions
        "order_by": "score desc",
        "format": "json",
    }
    if jurisdiction:
        params["court"] = jurisdiction
    if date_from:
        params["filed_after"] = date_from
    if date_to:
        params["filed_before"] = date_to

    headers = {"Authorization": f"Token {settings.courtlistener_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{COURTLISTENER_BASE}/search/",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])[:top_k]
            return [
                {
                    "case_name": r.get("caseName", ""),
                    "court": r.get("court", ""),
                    "date_filed": r.get("dateFiled", ""),
                    "url": f"https://www.courtlistener.com{r.get('absolute_url', '')}",
                    "snippet": r.get("snippet", ""),
                    "source": "courtlistener",
                }
                for r in results
            ]
    except Exception:
        return None


async def _search_govinfo(query: str, top_k: int) -> Optional[List[Dict[str, Any]]]:
    """Query GovInfo search API. Returns None on any error."""
    if not settings.govinfo_api_key:
        return None  # No key configured — skip

    params = {
        "query": query,
        "pageSize": top_k,
        "offsetMark": "*",
        "api_key": settings.govinfo_api_key,
        "resultLevel": "default",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GOVINFO_BASE}/search",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])[:top_k]
            return [
                {
                    "title": r.get("title", ""),
                    "collection": r.get("collectionCode", ""),
                    "date_issued": r.get("dateIssued", ""),
                    "url": r.get("packageLink", ""),
                    "snippet": r.get("context", {}).get("snippet", ""),
                    "source": "govinfo",
                }
                for r in results
            ]
    except Exception:
        return None
