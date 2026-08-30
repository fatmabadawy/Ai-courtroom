PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    hashed_pw TEXT NOT NULL,
    full_name TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    provenance_type TEXT NOT NULL CHECK (provenance_type IN ('USER_PROVIDED','PUBLIC_LEGAL_SOURCE','SYNTHETIC')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','paused','completed','error')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_parties (
    party_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('plaintiff','defendant','witness','other')),
    description TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    content_hash TEXT,
    extracted_text TEXT,
    document_type TEXT NOT NULL DEFAULT 'other',
    supersedes_document_id TEXT REFERENCES documents(document_id),
    upload_status TEXT NOT NULL DEFAULT 'pending' CHECK (upload_status IN ('pending','uploaded','processing','processed','failed')),
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS documents_case_content_hash_unique
    ON documents(case_id, content_hash) WHERE content_hash IS NOT NULL;
CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding TEXT NOT NULL DEFAULT '[]',
    page_number INTEGER,
    section_label TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS document_chunks_case_idx ON document_chunks(case_id);
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    document_id TEXT REFERENCES documents(document_id) ON DELETE SET NULL,
    url TEXT,
    title TEXT,
    source_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    document_id TEXT REFERENCES documents(document_id) ON DELETE SET NULL,
    source_id TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    chunk_id TEXT REFERENCES document_chunks(chunk_id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    source_type TEXT NOT NULL,
    evidence_type TEXT,
    relevance_score REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS evidence_case_idx ON evidence(case_id);
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    statement TEXT NOT NULL,
    made_by TEXT NOT NULL CHECK (made_by IN ('prosecution','defense','intake')),
    status TEXT NOT NULL DEFAULT 'UNVERIFIED' CHECK (status IN ('SUPPORTED','CONTRADICTED','PARTIALLY_SUPPORTED','UNVERIFIED')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
    PRIMARY KEY (claim_id, evidence_id)
);
CREATE TABLE IF NOT EXISTS arguments (
    argument_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    argument TEXT NOT NULL,
    evidence_ids TEXT NOT NULL DEFAULT '[]',
    source_ids TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('prosecution','defense')),
    round INTEGER NOT NULL DEFAULT 1,
    responds_to_argument_id TEXT REFERENCES arguments(argument_id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fact_checks (
    fact_check_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('SUPPORTED','CONTRADICTED','PARTIALLY_SUPPORTED','UNVERIFIED')),
    supporting_evidence_ids TEXT NOT NULL DEFAULT '[]',
    contradicting_evidence_ids TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL,
    reasoning TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_quality (
    evidence_id TEXT PRIMARY KEY REFERENCES evidence(evidence_id) ON DELETE CASCADE,
    reliability REAL NOT NULL, directness REAL NOT NULL, relevance REAL NOT NULL,
    corroboration REAL NOT NULL, recency REAL NOT NULL, authenticity_notes TEXT,
    composite_score REAL NOT NULL, methodology_version TEXT NOT NULL DEFAULT 'v1',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cross_examinations (
    cross_examination_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    round INTEGER NOT NULL,
    challenger TEXT NOT NULL CHECK (challenger = 'cross_examiner'),
    target_argument_id TEXT NOT NULL REFERENCES arguments(argument_id) ON DELETE CASCADE,
    question TEXT NOT NULL, response TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('strengthened','weakened','unchanged')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verdicts (
    verdict_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    finding TEXT NOT NULL, reasoning TEXT NOT NULL, confidence REAL NOT NULL,
    judge_profile TEXT NOT NULL,
    supporting_evidence_ids TEXT NOT NULL DEFAULT '[]',
    opposing_evidence_ids TEXT NOT NULL DEFAULT '[]',
    unresolved_questions TEXT NOT NULL DEFAULT '[]',
    disclaimer TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verdict_evidence (
    verdict_id TEXT NOT NULL REFERENCES verdicts(verdict_id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
    relation TEXT NOT NULL CHECK (relation IN ('supporting','opposing')),
    PRIMARY KEY (verdict_id, evidence_id, relation)
);
CREATE TABLE IF NOT EXISTS agent_messages (
    message_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL, event_type TEXT NOT NULL, content TEXT NOT NULL,
    evidence_refs TEXT NOT NULL DEFAULT '[]', confidence REAL, timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS agent_messages_case_timestamp_idx ON agent_messages(case_id, timestamp);
CREATE TABLE IF NOT EXISTS case_events (
    event_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    description TEXT NOT NULL, event_date TEXT, evidence_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trial_state (
    case_id TEXT PRIMARY KEY REFERENCES cases(case_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending', round INTEGER NOT NULL DEFAULT 0,
    state_snapshot TEXT, updated_at TEXT NOT NULL
);
