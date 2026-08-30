"""
backend/app/api/dependencies/auth.py
──────────────────────────────────────
FastAPI dependency for authenticated routes.

Currently bridges to auth_mock.py (Member E internal).
When Member A ships database/auth.py, replace the import at the top:

  # BEFORE (mock)
  from backend.app.api.dependencies.auth_mock import decode_access_token

  # AFTER (Member A's real module)
  from backend.app.database.auth import decode_access_token
"""
from __future__ import annotations

from typing import Dict, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.api.database.adapter import get_user_by_id
from backend.app.api.dependencies.auth_mock import decode_access_token  # ← swap to A's module when ready

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Dict[str, str]:
    """
    Validates Bearer JWT and returns the current user dict.
    Raises 401 if missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[Dict[str, str]]:
    """Returns user dict or None — used for routes that optionally require auth."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
