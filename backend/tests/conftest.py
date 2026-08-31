"""
backend/tests/conftest.py
──────────────────────────
Shared pytest fixtures for Member E's API tests.
Uses a per-test temp SQLite file so each test gets a fresh, isolated DB.
"""
from __future__ import annotations

import os
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Force mock mode BEFORE any app imports
os.environ["USE_MOCK_GRAPH"] = "true"
os.environ["USE_MOCK_RAG"] = "true"
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only"
os.environ["N8N_SERVICE_TOKEN"] = "test_n8n_token"

from backend.app.api.main import app
from backend.app.api.database import adapter as db_module
from backend.app.api.config import get_settings


@pytest_asyncio.fixture(autouse=True)
async def _fresh_db(tmp_path):
    """
    Give each test a brand-new SQLite file so connections never share state.

    The consolidated `backend.app.database.client` (re-exported here as
    `db_module`) reads its DB location from the `DATABASE_URL` / `SQLITE_PATH`
    env vars at call time (see `client.database_path()`), not from a cached
    settings object — so the fixture patches those env vars instead of a
    `settings.sqlite_path` attribute that no longer exists on this module.
    """
    db_file = str(tmp_path / "test.db")
    settings = get_settings()
    original_path = settings.sqlite_path
    settings.sqlite_path = db_file

    original_database_url = os.environ.get("DATABASE_URL")
    original_sqlite_path = os.environ.get("SQLITE_PATH")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    os.environ["SQLITE_PATH"] = db_file

    await db_module.init_db()
    yield

    settings.sqlite_path = original_path
    if original_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_database_url
    if original_sqlite_path is None:
        os.environ.pop("SQLITE_PATH", None)
    else:
        os.environ["SQLITE_PATH"] = original_sqlite_path


@pytest_asyncio.fixture
async def client(_fresh_db):
    """Async ASGI test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    """Register a user and return Authorization headers."""
    resp = await client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "TestPass123!", "full_name": "Test User"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def test_case(client: AsyncClient, auth_headers):
    """Create and return a test case."""
    resp = await client.post(
        "/cases",
        json={"title": "Test Case", "description": "A test contract dispute.", "provenance_type": "USER_PROVIDED"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
