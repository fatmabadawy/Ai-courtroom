"""
backend/app/api/services/evidence_service.py
──────────────────────────────────────────────
Builds the evidence graph payload and replay response.
Performs joins across claims → claim_evidence → evidence → documents/sources.

All joins happen HERE — the frontend only visualises the result.
"""
from __future__ import annotations

from typing import List

from backend.app.api.database import adapter as db
from backend.app.api.config import get_settings
from backend.app.api.schemas import (
    AgentMessage,
    EvidenceGraphResponse,
    GraphEdge,
    GraphNode,
    ReplayResponse,
)

settings = get_settings()


async def build_evidence_graph(case_id: str) -> EvidenceGraphResponse:
    """
    Construct node/edge JSON payload:
    Claim → Evidence → Source → Document
    """
    claims = await db.list_claims(case_id)
    evidence_list = await db.list_evidence(case_id)
    documents = await db.list_documents(case_id)
    sources = await db.list_sources(case_id)
    links = await db.list_claim_evidence_links(case_id)

    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []

    seen_node_ids: set[str] = set()

    def add_node(node: GraphNode) -> None:
        if node.id not in seen_node_ids:
            nodes.append(node)
            seen_node_ids.add(node.id)

    # Claim nodes
    for claim in claims:
        add_node(GraphNode(
            id=claim["claim_id"],
            type="claim",
            label=claim["statement"][:80],
            data={"status": claim.get("status", "UNVERIFIED"), "made_by": claim.get("made_by", "")},
        ))

    # Evidence nodes
    ev_map = {e["evidence_id"]: e for e in evidence_list}
    for ev in evidence_list:
        add_node(GraphNode(
            id=ev["evidence_id"],
            type="evidence",
            label=ev["content"][:80],
            data={"source_type": ev.get("source_type", ""), "relevance_score": ev.get("relevance_score", 0)},
        ))

    # Claim → Evidence edges
    for link in links:
        edges.append(GraphEdge(
            id=f"ce-{link['claim_id']}-{link['evidence_id']}",
            source=link["claim_id"],
            target=link["evidence_id"],
            label="supports",
        ))

    # Document nodes and Evidence → Document edges
    doc_map = {d["document_id"]: d for d in documents}
    for ev in evidence_list:
        if ev.get("document_id") and ev["document_id"] in doc_map:
            doc = doc_map[ev["document_id"]]
            add_node(GraphNode(
                id=doc["document_id"],
                type="document",
                label=doc["filename"],
                data={"content_type": doc.get("content_type", "")},
            ))
            edges.append(GraphEdge(
                id=f"ed-{ev['evidence_id']}-{doc['document_id']}",
                source=ev["evidence_id"],
                target=doc["document_id"],
                label="from",
            ))

    # Source nodes and Evidence → Source edges
    for src in sources:
        add_node(GraphNode(
            id=src["source_id"],
            type="source",
            label=src.get("title") or src.get("url") or src["source_id"],
            data={"source_type": src.get("source_type", "")},
        ))
        if src.get("document_id") and src["document_id"] in doc_map:
            edges.append(GraphEdge(
                id=f"sd-{src['source_id']}-{src['document_id']}",
                source=src["source_id"],
                target=src["document_id"],
                label="cited_in",
            ))

    # If no real data exists (mock mode), inject the mock evidence graph
    if not nodes:
        nodes, edges = _mock_graph_nodes_edges(case_id)

    return EvidenceGraphResponse(case_id=case_id, nodes=nodes, edges=edges)


def _mock_graph_nodes_edges(case_id: str):
    """Return illustrative mock graph when the DB has no data yet."""
    nodes = [
        GraphNode(id="CL-001", type="claim", label="Bob Ltd failed to deliver on time", data={"status": "SUPPORTED"}),
        GraphNode(id="CL-002", type="claim", label="Spec change caused the delay", data={"status": "PARTIALLY_SUPPORTED"}),
        GraphNode(id="EV-MOCK-1", type="evidence", label="Contract delivery clause (p.1)", data={"source_type": "SYNTHETIC", "relevance_score": 0.9}),
        GraphNode(id="EV-MOCK-2", type="evidence", label="Spec change email (p.2)", data={"source_type": "SYNTHETIC", "relevance_score": 0.8}),
        GraphNode(id="EV-MOCK-3", type="evidence", label="Delivery log entry", data={"source_type": "SYNTHETIC", "relevance_score": 0.75}),
        GraphNode(id="DOC-MOCK-1", type="document", label="contract.pdf", data={"content_type": "application/pdf"}),
        GraphNode(id="DOC-MOCK-2", type="document", label="email_thread.pdf", data={"content_type": "application/pdf"}),
    ]
    edges = [
        GraphEdge(id="e1", source="CL-001", target="EV-MOCK-1", label="supports"),
        GraphEdge(id="e2", source="CL-002", target="EV-MOCK-2", label="supports"),
        GraphEdge(id="e3", source="EV-MOCK-1", target="DOC-MOCK-1", label="from"),
        GraphEdge(id="e4", source="EV-MOCK-3", target="DOC-MOCK-1", label="from"),
        GraphEdge(id="e5", source="EV-MOCK-2", target="DOC-MOCK-2", label="from"),
    ]
    return nodes, edges


async def build_replay(case_id: str) -> ReplayResponse:
    """Return agent messages in chronological order for the replay view."""
    rows = await db.list_agent_messages(case_id)
    events = [
        AgentMessage(
            message_id=r["message_id"],
            case_id=r["case_id"],
            agent_name=r["agent_name"],
            event_type=r["event_type"],
            content=r["content"],
            evidence_refs=r.get("evidence_refs", []),
            confidence=r.get("confidence"),
            timestamp=r["timestamp"],
        )
        for r in rows
    ]
    return ReplayResponse(case_id=case_id, events=events)
