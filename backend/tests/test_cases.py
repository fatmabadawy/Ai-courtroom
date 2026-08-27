"""
backend/tests/test_cases.py
─────────────────────────────
Tests for /cases endpoints.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_case(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/cases",
        json={"title": "Contract Dispute", "description": "A dispute about deliverables.", "provenance_type": "USER_PROVIDED"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Contract Dispute"
    assert "case_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_list_cases(client: AsyncClient, auth_headers):
    await client.post(
        "/cases",
        json={"title": "Case A", "description": "Desc A", "provenance_type": "USER_PROVIDED"},
        headers=auth_headers,
    )
    await client.post(
        "/cases",
        json={"title": "Case B", "description": "Desc B", "provenance_type": "USER_PROVIDED"},
        headers=auth_headers,
    )
    resp = await client.get("/cases", headers=auth_headers)
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) >= 2


@pytest.mark.asyncio
async def test_get_case(client: AsyncClient, auth_headers, test_case):
    case_id = test_case["case_id"]
    resp = await client.get(f"/cases/{case_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["case_id"] == case_id


@pytest.mark.asyncio
async def test_get_case_not_found(client: AsyncClient, auth_headers):
    resp = await client.get("/cases/nonexistent-id", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_case(client: AsyncClient, auth_headers, test_case):
    case_id = test_case["case_id"]
    resp = await client.delete(f"/cases/{case_id}", headers=auth_headers)
    assert resp.status_code == 204
    # Verify it's gone
    resp2 = await client.get(f"/cases/{case_id}", headers=auth_headers)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_case_isolation_between_users(client: AsyncClient):
    """User A cannot see User B's cases."""
    # Register user A
    reg_a = await client.post(
        "/auth/register",
        json={"email": "usera@example.com", "password": "Password1!"},
    )
    headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}
    case_resp = await client.post(
        "/cases",
        json={"title": "User A Case", "description": "private", "provenance_type": "USER_PROVIDED"},
        headers=headers_a,
    )
    case_id = case_resp.json()["case_id"]

    # Register user B
    reg_b = await client.post(
        "/auth/register",
        json={"email": "userb@example.com", "password": "Password1!"},
    )
    headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

    resp = await client.get(f"/cases/{case_id}", headers=headers_b)
    assert resp.status_code == 404  # B cannot see A's case


@pytest.mark.asyncio
async def test_search_public_no_key(client: AsyncClient, auth_headers):
    """When no API keys are configured, returns insufficient_public_data."""
    resp = await client.post(
        "/cases/search-public",
        json={"query": "contract breach"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("insufficient_public_data") is True
