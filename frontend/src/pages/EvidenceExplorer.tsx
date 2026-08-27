import React from 'react'
import { useParams, Link } from 'react-router-dom'
import { ShieldCheck, GitGraph, FileText } from 'lucide-react'
import { useQuery } from '../shims/reactQuery'
import { evidenceApi } from '../api/client'
import { EvidenceCard } from '../components/EvidenceCard'

export const EvidenceExplorer: React.FC = () => {
  const { caseId = '' } = useParams<{ caseId: string }>()

  const { data: evidenceList, isLoading, error } = useQuery({
    queryKey: ['evidence', caseId],
    queryFn: () => evidenceApi.list(caseId),
    enabled: !!caseId,
  })

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Evidence Explorer</h2>
          <p className="text-sm text-slate-400 mt-1">
            Browse indexed chunks, extracted claims, and relevance scores retrieved via RAG
          </p>
        </div>

        <Link
          to={`/cases/${caseId}/graph`}
          className="flex items-center space-x-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
        >
          <GitGraph className="w-4 h-4 text-blue-400" />
          <span>View Visual Graph</span>
        </Link>
      </div>

      {isLoading ? (
        <div className="p-12 text-center text-slate-400">Loading evidence items...</div>
      ) : error ? (
        <div className="p-6 rounded-xl bg-red-950/30 border border-red-800 text-red-300 text-sm">
          Failed to load evidence for this case.
        </div>
      ) : !evidenceList || evidenceList.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-900/40 space-y-3">
          <ShieldCheck className="w-10 h-10 text-slate-600 mx-auto" />
          <h4 className="font-semibold text-white">No evidence retrieved yet</h4>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Once a trial runs or documents are ingested, indexed evidence items will appear here.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {evidenceList.map((ev) => (
            <EvidenceCard key={ev.evidence_id} evidence={ev} />
          ))}
        </div>
      )}
    </div>
  )
}
