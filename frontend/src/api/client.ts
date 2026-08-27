/**
 * frontend/src/api/client.ts
 * ───────────────────────────
 * Typed Axios wrapper for all backend API calls.
 * The frontend ONLY communicates with the FastAPI backend — never directly
 * with databases, RAG, or LangGraph.
 *
 * All token management is handled here so no component touches localStorage directly.
 */
import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import type {
  CaseRow,
  DocumentRow,
  EvidenceGraphResponse,
  EvidenceResult,
  ReplayResponse,
  TokenResponse,
  TrialStateResponse,
  Verdict,
  HumanIntervention,
} from '../types/schemas'

const BASE_URL = '/api'  // proxied to http://localhost:8000 via vite.config.ts

const TOKEN_KEY = 'ac_access_token'
const REFRESH_KEY = 'ac_refresh_token'

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

function saveTokens(tokens: TokenResponse): void {
  localStorage.setItem(TOKEN_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token)
}

function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

const api: AxiosInstance = axios.create({ baseURL: BASE_URL })

// Attach access token to every request
api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auto-refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean }
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = localStorage.getItem(REFRESH_KEY)
      if (refresh) {
        try {
          const res = await axios.post<TokenResponse>(`${BASE_URL}/auth/refresh`, {
            refresh_token: refresh,
          })
          saveTokens(res.data)
          return api(original)
        } catch {
          clearTokens()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  },
)

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  register: async (email: string, password: string, fullName?: string) => {
    const res = await api.post<TokenResponse>('/auth/register', {
      email,
      password,
      full_name: fullName,
    })
    saveTokens(res.data)
    return res.data
  },

  login: async (email: string, password: string) => {
    const res = await api.post<TokenResponse>('/auth/login', { email, password })
    saveTokens(res.data)
    return res.data
  },

  logout: () => {
    clearTokens()
    window.location.href = '/login'
  },

  isLoggedIn: () => !!getToken(),
}

// ── Cases ─────────────────────────────────────────────────────────────────────

export const casesApi = {
  create: async (title: string, description: string, provenanceType = 'USER_PROVIDED') => {
    const res = await api.post<CaseRow>('/cases', {
      title,
      description,
      provenance_type: provenanceType,
    })
    return res.data
  },

  list: async () => {
    const res = await api.get<CaseRow[]>('/cases')
    return res.data
  },

  get: async (caseId: string) => {
    const res = await api.get<CaseRow>(`/cases/${caseId}`)
    return res.data
  },

  delete: async (caseId: string) => {
    await api.delete(`/cases/${caseId}`)
  },

  searchPublic: async (query: string, options?: {
    jurisdiction?: string
    date_from?: string
    date_to?: string
    top_k?: number
  }) => {
    const res = await api.post('/cases/search-public', { query, ...options })
    return res.data
  },
}

// ── Documents ─────────────────────────────────────────────────────────────────

export const documentsApi = {
  upload: async (caseId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    const res = await api.post<DocumentRow>(`/cases/${caseId}/documents`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  list: async (caseId: string) => {
    const res = await api.get<DocumentRow[]>(`/cases/${caseId}/documents`)
    return res.data
  },

  get: async (documentId: string) => {
    const res = await api.get<DocumentRow>(`/documents/${documentId}`)
    return res.data
  },
}

// ── Trial ─────────────────────────────────────────────────────────────────────

export const trialApi = {
  start: async (caseId: string, judgeProfile: 'strict' | 'balanced' | 'skeptical' = 'balanced') => {
    const res = await api.post('/trial/start', {
      case_id: caseId,
      judge_profile: judgeProfile,
    })
    return res.data
  },

  getState: async (caseId: string): Promise<TrialStateResponse> => {
    const res = await api.get<TrialStateResponse>('/trial/state', {
      params: { case_id: caseId },
    })
    return res.data
  },

  intervene: async (caseId: string, intervention: HumanIntervention) => {
    const res = await api.post('/trial/intervene', {
      case_id: caseId,
      intervention,
    })
    return res.data
  },

  resume: async (caseId: string) => {
    const res = await api.post('/trial/resume', { case_id: caseId })
    return res.data
  },
}

// ── Evidence ──────────────────────────────────────────────────────────────────

export const evidenceApi = {
  list: async (caseId: string) => {
    const res = await api.get<EvidenceResult[]>(`/cases/${caseId}/evidence`)
    return res.data
  },

  get: async (evidenceId: string) => {
    const res = await api.get<EvidenceResult>(`/evidence/${evidenceId}`)
    return res.data
  },

  graph: async (caseId: string): Promise<EvidenceGraphResponse> => {
    const res = await api.get<EvidenceGraphResponse>(`/cases/${caseId}/evidence-graph`)
    return res.data
  },

  replay: async (caseId: string): Promise<ReplayResponse> => {
    const res = await api.get<ReplayResponse>(`/cases/${caseId}/replay`)
    return res.data
  },

  verdict: async (caseId: string): Promise<Verdict> => {
    const res = await api.get<Verdict>(`/cases/${caseId}/verdict`)
    return res.data
  },

  verdicts: async (caseId: string): Promise<Verdict[]> => {
    const res = await api.get<Verdict[]>(`/cases/${caseId}/verdicts`)
    return res.data
  },
}

export default api
