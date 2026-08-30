"""
backend/app/api/dependencies/auth_mock.py
──────────────────────────────────────────
Member E internal mock auth helpers.
Provides JWT creation/verification until Member A ships database/auth.py.

When A's auth is ready, update auth.py to import from A's module instead of here.
This file should then be deleted or kept only as a reference.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from backend.app.api.config import get_settings

settings = get_settings()


def hash_password(plain: str) -> str:
    """Standard secure PBKDF2-HMAC-SHA256 password hash."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        plain.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return f"{salt}:{key.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify standard PBKDF2 hash."""
    try:
        salt, key_hex = hashed.split(":", 1)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            plain.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        )
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


def hash_token(token: str) -> str:
    """SHA-256 hash for storing refresh tokens in DB without exposing the raw value."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "type": "access",
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Returns (raw_token, expires_at_iso)."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_hex(16),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, expire.isoformat()


def decode_access_token(token: str) -> Optional[dict]:
    """Returns payload dict or None on failure."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[str]:
    """Returns user_id or None on failure."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "refresh":
            return None
        return payload.get("sub")
    except JWTError:
        return None
