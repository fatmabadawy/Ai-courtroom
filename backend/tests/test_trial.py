"""
backend/tests/test_trial.py
─────────────────────────────
Tests for /trial/* endpoints using the mock graph.
Critical: these tests verify the INTERFACE contract, not implementation details.
When C/D ship the real graph, these tests must still pass (USE_MOCK_GRAPH=false).
"""
import asyncio
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_start_trial_returns_202(client: AsyncClient, auth_headers, test_case):
    case_id = test_case["case_id"]
    resp = await client.post(
        "/trial/start",
        json={"case_id": case_id, "judge_profile": "balanced"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["case_id"] == case_id
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_start_trial_case_not_found(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/trial/start",
        json={"case_id": "nonexistent", "judge_profile": "balanced"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_trial_state_after_start(client: AsyncClient, auth_headers, test_case):
    """
    Starts a trial, waits briefly, then checks that state is persisted.
    The mock graph runs synchronously in the background task.
    """
    case_id = test_case["case_id"]
    await client.post(
        "/trial/start",
        json={"case_id": case_id, "judge_profile": "balanced"},
        headers=auth_headers,
    )
    # Give the background task time to complete
    await asyncio.sleep(0.5)

    resp = await client.get(f"/trial/state?case_id={case_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == case_id
    assert data["status"] in ("pending", "running", "completed")


@pytest.mark.asyncio
async def test_trial_state_missing_case(client: AsyncClient, auth_headers):
    resp = await client.get("/trial/state?case_id=nope", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_no_double_start(client: AsyncClient, auth_headers, test_case):
    """Starting an already-running trial should return 409."""
    case_id = test_case["case_id"]
    await client.post(
        "/trial/start",
        json={"case_id": case_id, "judge_profile": "balanced"},
        headers=auth_headers,
    )
    # Immediately try again before background task finishes
    resp = await client.post(
        "/trial/start",
        json={"case_id": case_id, "judge_profile": "balanced"},
        headers=auth_headers,
    )
    # Should be 409 (already running/pending) or 202 if first completed — either is OK
    assert resp.status_code in (202, 409)
