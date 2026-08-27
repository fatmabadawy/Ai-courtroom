import React from 'react'
import { useParams, Link } from 'react-router-dom'
import { Award, Scale, History, ArrowLeft } from 'lucide-react'
import { useQuery } from '../shims/reactQuery'
import { evidenceApi } from '../api/client'
import { VerdictPanel } from '../components/VerdictPanel'

export const Verdict: React.FC = () => {
  const { caseId = '' } = useParams<{ caseId: string }>()

  const { data: verdict, isLoading, error } = useQuery({
    queryKey: ['verdict', caseId],
    queryFn: () => evidenceApi.verdict(caseId),
    enabled: !!caseId,
  })

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold text-white tracking-tight">Final Court Verdict</h2>
          <p className="text-sm text-slate-400">
            Synthesized judicial decision based on evidence quality and debate rounds
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            to={`/cases/${caseId}/courtroom`}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Courtroom</span>
          </Link>
          <Link
            to={`/cases/${caseId}/replay`}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
          >
            <History className="w-3.5 h-3.5" />
            <span>View Replay</span>
          </Link>
        </div>
      </div>

      {isLoading ? (
        <div className="p-12 text-center text-slate-400">Loading trial verdict...</div>
      ) : error || !verdict ? (
        <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-900/40 space-y-4">
          <Scale className="w-10 h-10 text-slate-600 mx-auto" />
          <h4 className="font-semibold text-white">No verdict rendered yet</h4>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            The trial must be initiated and run to completion before a verdict can be synthesized.
          </p>
          <Link
            to={`/cases/${caseId}/courtroom`}
            className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors"
          >
            <Scale className="w-3.5 h-3.5" />
            <span>Go to Courtroom</span>
          </Link>
        </div>
      ) : (
        <VerdictPanel verdict={verdict} />
      )}
    </div>
  )
}
