"""
backend/tests/test_contracts.py
─────────────────────────────────
CONTRACT TESTS — verify that API responses match INTERFACES.md §3 schemas exactly.

These tests import the shared Pydantic models and validate actual API responses
against them. They should pass regardless of whether USE_MOCK_GRAPH is true or false.
If they fail after swapping in the real graph, that is a C/D interface violation —
NOT a bug in Member E's code.
"""
import asyncio
import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from backend.app.models.schemas import (
    EvidenceGraphResponse,
    ReplayResponse,
    TokenResponse,
    Verdict,
)


@pytest.mark.asyncio
async def test_token_response_matches_schema(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        json={"email": "schema_test@example.com", "password": "Password1!"},
    )
    assert resp.status_code == 201
    # This will raise ValidationError if the response doesn't match the schema
    TokenResponse(**resp.json())


@pytest.mark.asyncio
async def test_evidence_graph_matches_schema(client: AsyncClient, auth_headers, test_case):
    case_id = test_case["case_id"]
    resp = await client.get(f"/cases/{case_id}/evidence-graph", headers=auth_headers)
    assert resp.status_code == 200
    EvidenceGraphResponse(**resp.json())


@pytest.mark.asyncio
async def test_replay_matches_schema(client: AsyncClient, auth_headers, test_case):
    case_id = test_case["case_id"]
    resp = await client.get(f"/cases/{case_id}/replay", headers=auth_headers)
    assert resp.status_code == 200
    ReplayResponse(**resp.json())


@pytest.mark.asyncio
async def test_verdict_matches_schema_when_present(client: AsyncClient, auth_headers, test_case):
    """If a verdict exists, it must deserialise cleanly into the shared Verdict schema."""
    case_id = test_case["case_id"]
    await client.post(
        "/trial/start",
        json={"case_id": case_id, "judge_profile": "balanced"},
        headers=auth_headers,
    )
    await asyncio.sleep(0.5)

    resp = await client.get(f"/cases/{case_id}/verdict", headers=auth_headers)
    if resp.status_code == 200:
        try:
            Verdict(**resp.json())
        except ValidationError as exc:
            pytest.fail(
                f"Verdict response does not match INTERFACES.md §3 Verdict schema:\n{exc}"
            )


@pytest.mark.asyncio
async def test_health_exposes_mock_flags(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "mock_graph" in data
    assert "mock_rag" in data
    assert data["mock_graph"] is True
    assert data["mock_rag"] is True
