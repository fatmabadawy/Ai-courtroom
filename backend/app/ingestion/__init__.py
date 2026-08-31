"""
backend/app/ingestion/
────────────────────────
Plan B — document ingestion pipeline.

Parses uploaded documents (PDF/DOCX/TXT), chunks the extracted text, embeds
each chunk with a local sentence-transformers model, and persists chunks +
evidence rows so backend/app/rag/retrieve_real.py can search over them.

Entry point: `ingestion.ingest.ingest_document(document_id, case_id, file_path)`
— this is exactly the hook `backend/app/api/routers/documents.py` already
looks for (`from backend.app.ingestion.ingest import ingest_document`).
"""
