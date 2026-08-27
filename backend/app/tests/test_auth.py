"""
backend/tests/test_auth.py
───────────────────────────
Tests for /auth/register, /auth/login, /auth/refresh.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "Password1!", "full_name": "New User"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "Password1!"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "Password1!"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "Password1!"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "wp@example.com", "password": "Password1!"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "wp@example.com", "password": "WrongPassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    reg = await client.post(
        "/auth/register",
        json={"email": "refresh@example.com", "password": "Password1!"},
    )
    refresh_token = reg.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    # Original refresh token should now be invalid (rotated)
    resp2 = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client: AsyncClient):
    resp = await client.get("/cases")
    assert resp.status_code == 401
