import React from 'react'
import { useParams } from 'react-router-dom'
import { History, Clock } from 'lucide-react'
import { useQuery } from '../shims/reactQuery'
import { evidenceApi } from '../api/client'
import { ReplayTimeline } from '../components/ReplayTimeline'

export const TrialReplay: React.FC = () => {
  const { caseId = '' } = useParams<{ caseId: string }>()

  const { data: replayData, isLoading, error } = useQuery({
    queryKey: ['replay', caseId],
    queryFn: () => evidenceApi.replay(caseId),
    enabled: !!caseId,
  })

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Trial Event Replay</h2>
        <p className="text-sm text-slate-400 mt-1">
          True chronological sequence of agent arguments, fact-checks, and rulings
        </p>
      </div>

      {isLoading ? (
        <div className="p-12 text-center text-slate-400">Loading trial event replay...</div>
      ) : error ? (
        <div className="p-6 rounded-xl bg-red-950/30 border border-red-800 text-red-300 text-sm">
          Failed to load trial replay data.
        </div>
      ) : (
        <ReplayTimeline events={replayData?.events || []} />
      )}
    </div>
  )
}
