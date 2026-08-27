# PLAN_B — Document Ingestion & RAG

**Owns:** `backend/app/ingestion/`, `backend/app/rag/`.
**Read first:** `INTERFACES.md` §2, §6, §8.
**Depends on:** A's DDL only (not the hosted instance — run the DDL locally on day 1, don't wait for A).

This corresponds to Phases 3–4 of the master `IMPLEMENTATION_PLAN.md` (§6, §7, §9 for full detail).

## Day 1 priority

1. Spin up your own local `pgvector` Postgres container using A's migration file (don't wait for A's hosted Supabase).
2. Ship `backend/app/rag/retrieve_mock.py` (exact code in `INTERFACES.md §6`) **within the first 2 days** — this is the single highest-leverage thing you can do, since it unblocks C and D immediately.

## Tasks — Ingestion

- [ ] Parsers: PDF (`pymupdf`), DOCX (`python-docx`), TXT, per master §6.
- [ ] Scanned-page detection heuristic + OCR fallback (`pytesseract`).
- [ ] Text normalization, metadata extraction (dates, page numbers, section labels).
- [ ] Document classification (contract/email/witness statement/invoice/opinion/other) — simple rule-based or LLM-assisted classifier is fine for MVP.
- [ ] Chunker (~500–800 tokens, 15% overlap), writes to `document_chunks`.
- [ ] Embedding job using `BAAI/bge-small-en-v1.5` (local, 384-dim) — must match the `vector(384)` column A created.
- [ ] Evidence promotion: turn qualifying chunks into `evidence` rows (source_type, evidence_type, initial scores).
- [ ] Duplicate detection via `content_hash`; versioning via `supersedes_document_id`.
- [ ] Malformed-file handling: per-file try/except, never crash the batch.

## Tasks — RAG

- [ ] `backend/app/rag/retrieve.py` implementing the exact signature in `INTERFACES.md §6`.
- [ ] Metadata filtering (`evidence_type`, `date`, `provenance_type`).
- [ ] Mandatory `case_id` scoping on every query (never a cross-case leak).
- [ ] (V1, don't block MVP on this) reranker, hybrid full-text + vector search.

## Interfaces you must ship (per `INTERFACES.md`)

- `retrieve_mock.py` — day 2.
- Real `retrieve(case_id, query, top_k, filters) -> List[EvidenceResult]` matching the `EvidenceResult` schema in `INTERFACES.md §3` exactly — C and D's code will be written against this schema and will break if you deviate (e.g., don't rename `relevance_score`).
- An `ingest_document(file, case_id) -> Document` function E's upload endpoint calls directly.

## Testing

- Unit tests per parser type, using synthetic files you create (don't wait on A's fixture for these).
- Once A's fixture case (`data/demo_cases/case_001/`) is available: run full ingestion → confirm chunk count, embeddings present, and `retrieve()` returns the expected top result for a known query against that fixture.
- Duplicate-upload test (expect 409-equivalent rejection at the service layer).

## Acceptance criteria (mirrors master §39 Phase 3)

- [ ] PDF uploads successfully
- [ ] Text extraction works
- [ ] OCR works for a scanned PDF
- [ ] Page numbers preserved
- [ ] Document stored via A's `database/client.py`
- [ ] Chunks generated
- [ ] Embeddings generated (384-dim, matches schema)
- [ ] Vector search returns relevant chunks for a known query on the fixture case
- [ ] `retrieve_mock.py` shipped within 2 days, real `retrieve()` passes the same test suite as the mock

## Integration notes

Your real `retrieve()` must be a drop-in replacement for your own mock — same signature, same schema. C and D will flip `USE_MOCK_RAG=false` at the Friday integration checkpoint; if that breaks anything, it's a signal your real implementation drifted from the contract, not that C/D did something wrong.
