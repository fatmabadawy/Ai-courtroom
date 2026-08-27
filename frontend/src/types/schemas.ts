/**
 * frontend/src/types/schemas.ts
 * TypeScript mirror of INTERFACES.md §3 Pydantic schemas.
 * Keep in sync with backend/app/models/schemas.py.
 */

export type PartyRole = 'plaintiff' | 'defendant' | 'witness' | 'other'
export type ClaimStatus = 'SUPPORTED' | 'CONTRADICTED' | 'PARTIALLY_SUPPORTED' | 'UNVERIFIED'
export type SourceType = 'USER_PROVIDED' | 'PUBLIC_LEGAL_SOURCE' | 'WEB_SOURCE' | 'SYNTHETIC'
export type ProvenanceType = 'USER_PROVIDED' | 'PUBLIC_LEGAL_SOURCE' | 'SYNTHETIC'
export type JudgeProfileName = 'strict' | 'balanced' | 'skeptical'
export type TrialStatus = 'pending' | 'running' | 'paused' | 'completed' | 'error'

export interface Party {
  party_id: string
  name: string
  role: PartyRole
  description?: string
}

export interface CaseEvent {
  event_id: string
  description: string
  date?: string
  evidence_ids: string[]
}

export interface Claim {
  claim_id: string
  statement: string
  made_by: 'prosecution' | 'defense' | 'intake'
  related_evidence_ids: string[]
  status: ClaimStatus
}

export interface StructuredCase {
  case_id: string
  title: string
  description: string
  parties: Party[]
  claims: Claim[]
  events: CaseEvent[]
  legal_questions: string[]
  evidence_ids: string[]
  unknowns: string[]
  contradictions: string[]
  provenance_type: ProvenanceType
}

export interface EvidenceResult {
  evidence_id: string
  content: string
  source_type: SourceType
  document_id?: string
  document_page?: number
  relevance_score: number
}

export interface Argument {
  claim_id: string
  argument: string
  evidence_ids: string[]
  source_ids: string[]
  confidence: number
  side: 'prosecution' | 'defense'
  round: number
  responds_to_argument_id?: string
}

export interface FactCheck {
  claim_id: string
  status: ClaimStatus
  supporting_evidence_ids: string[]
  contradicting_evidence_ids: string[]
  confidence: number
  reasoning: string
}

export interface EvidenceQualityScore {
  evidence_id: string
  reliability: number
  directness: number
  relevance: number
  corroboration: number
  recency: number
  authenticity_notes?: string
  composite_score: number
  methodology_version: string
}

export interface CrossExaminationRound {
  round: number
  challenger: 'cross_examiner'
  target_argument_id: string
  question: string
  response: string
  outcome: 'strengthened' | 'weakened' | 'unchanged'
}

export interface JudgeProfile {
  name: JudgeProfileName
}

export interface Verdict {
  finding: string
  supporting_evidence_ids: string[]
  opposing_evidence_ids: string[]
  unresolved_questions: string[]
  reasoning: string
  confidence: number
  judge_profile: string
  disclaimer: string
}

export interface HumanIntervention {
  new_document_ids: string[]
  affected_claim_ids: string[]
  submitted_at: string
}

// API-layer types ─────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface CaseRow {
  case_id: string
  title: string
  description: string
  provenance_type: ProvenanceType
  owner_id: string
  created_at: string
  status: string
}

export interface DocumentRow {
  document_id: string
  case_id: string
  filename: string
  content_type: string
  size_bytes: number
  upload_status: string
  created_at: string
}

export interface TrialStateResponse {
  case_id: string
  status: TrialStatus
  round: number
  verdict?: Verdict
  state_snapshot?: Record<string, unknown>
}

// Evidence graph ──────────────────────────────────────────────────────────────

export type NodeType = 'claim' | 'evidence' | 'source' | 'document'

export interface GraphNode {
  id: string
  type: NodeType
  label: string
  data: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label?: string
}

export interface EvidenceGraphResponse {
  case_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// Replay ──────────────────────────────────────────────────────────────────────

export interface AgentMessage {
  message_id: string
  case_id: string
  agent_name: string
  event_type: string
  content: string
  evidence_refs: string[]
  confidence?: number
  timestamp: string
}

export interface ReplayResponse {
  case_id: string
  events: AgentMessage[]
}
