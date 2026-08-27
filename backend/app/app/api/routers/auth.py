"""
backend/app/api/routers/auth.py
────────────────────────────────
POST /auth/register  — create user
POST /auth/login     — issue access + refresh tokens
POST /auth/refresh   — rotate refresh token
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.api.database import adapter as db
from app.api.dependencies.auth_mock import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.schemas import (
    ErrorResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    existing = await db.get_user_by_email(body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "EMAIL_TAKEN", "message": "Email already registered"},
        )
    hashed = hash_password(body.password)
    user = await db.create_user(body.email, hashed, body.full_name)
    access_token = create_access_token(user["user_id"], user["email"])
    refresh_token, expires_at = create_refresh_token(user["user_id"])
    await db.store_refresh_token(user["user_id"], hash_token(refresh_token), expires_at)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = await db.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["hashed_pw"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
        )
    access_token = create_access_token(user["user_id"], user["email"])
    refresh_token, expires_at = create_refresh_token(user["user_id"])
    await db.store_refresh_token(user["user_id"], hash_token(refresh_token), expires_at)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest):
    token_hash = hash_token(body.refresh_token)
    stored = await db.get_refresh_token(token_hash)
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_REFRESH_TOKEN", "message": "Refresh token is invalid or expired"},
        )
    # Verify expiry
    expires_at = datetime.fromisoformat(stored["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        await db.delete_refresh_token(token_hash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "REFRESH_TOKEN_EXPIRED", "message": "Refresh token expired"},
        )
    user_id = decode_refresh_token(body.refresh_token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = await db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Rotate — delete old, issue new
    await db.delete_refresh_token(token_hash)
    new_access = create_access_token(user["user_id"], user["email"])
    new_refresh, new_expires = create_refresh_token(user["user_id"])
    await db.store_refresh_token(user["user_id"], hash_token(new_refresh), new_expires)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)
