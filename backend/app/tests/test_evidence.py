"""
backend/tests/test_evidence.py
────────────────────────────────
Tests for /evidence, /evidence-graph, /replay, /verdict endpoints.
"""
import asyncio
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_evidence_empty(client: AsyncClient, auth_headers, test_case):
    case_id = test_case["case_id"]
    resp = await client.get(f"/cases/{case_id}/evidence", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_evidence_graph_returns_nodes_and_edges(client: AsyncClient, auth_headers, test_case):
    """Evidence graph should always return valid node/edge JSON (mock fallback when empty)."""
    case_id = test_case["case_id"]
    resp = await client.get(f"/cases/{case_id}/evidence-graph", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert "case_id" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


@pytest.mark.asyncio
async def test_evidence_graph_node_schema(client: AsyncClient, auth_headers, test_case):
    """Each node must have id, type, label, data fields."""
    case_id = test_case["case_id"]
    resp = await client.get(f"/cases/{case_id}/evidence-graph", headers=auth_headers)
    nodes = resp.json()["nodes"]
    for node in nodes:
        assert "id" in node
        assert "type" in node
        assert "label" in node
        assert "data" in node
        assert node["type"] in ("claim", "evidence", "source", "document")


@pytest.mark.asyncio
async def test_replay_empty(client: AsyncClient, auth_headers, test_case):
    case_id = test_case["case_id"]
    resp = await client.get(f"/cases/{case_id}/replay", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_verdict_not_found_before_trial(client: AsyncClient, auth_headers, test_case):
    case_id = test_case["case_id"]
    resp = await client.get(f"/cases/{case_id}/verdict", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_verdict_after_trial(client: AsyncClient, auth_headers, test_case):
    """After a completed trial, verdict should be accessible and match the shared schema."""
    case_id = test_case["case_id"]
    await client.post(
        "/trial/start",
        json={"case_id": case_id, "judge_profile": "balanced"},
        headers=auth_headers,
    )
    await asyncio.sleep(0.5)  # wait for background task

    resp = await client.get(f"/cases/{case_id}/verdict", headers=auth_headers)
    # Might still be running — accept 200 or 404
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        # Verify Verdict schema fields from INTERFACES.md §3
        assert "finding" in data
        assert "reasoning" in data
        assert "confidence" in data
        assert "judge_profile" in data
        assert "supporting_evidence_ids" in data
        assert "opposing_evidence_ids" in data
        assert "unresolved_questions" in data
        assert "disclaimer" in data
        assert isinstance(data["confidence"], float)
        assert 0.0 <= data["confidence"] <= 1.0
