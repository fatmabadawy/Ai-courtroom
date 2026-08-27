import React from 'react'
import { Clock, Shield, Scale, Flame, CheckCircle2, UserCheck, Bell } from 'lucide-react'
import type { AgentMessage } from '../types/schemas'

export interface ReplayTimelineProps {
  events: AgentMessage[]
}

const agentIcons: Record<string, React.ReactNode> = {
  prosecution: <Flame className="w-4 h-4 text-red-400" />,
  defense: <Shield className="w-4 h-4 text-blue-400" />,
  fact_checker: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
  cross_examiner: <Scale className="w-4 h-4 text-purple-400" />,
  judge: <UserCheck className="w-4 h-4 text-indigo-400" />,
  system: <Clock className="w-4 h-4 text-slate-400" />,
  n8n: <Bell className="w-4 h-4 text-amber-400" />,
}

export const ReplayTimeline: React.FC<ReplayTimelineProps> = ({ events }) => {
  if (!events || events.length === 0) {
    return (
      <div className="p-8 text-center border border-slate-800 rounded-xl bg-slate-900/40 text-slate-400 text-sm">
        No trial events recorded yet. Run a trial to generate a replay timeline.
      </div>
    )
  }

  return (
    <div className="relative pl-6 border-l border-slate-800 space-y-6">
      {events.map((event, idx) => {
        const icon = agentIcons[event.agent_name.toLowerCase()] || <Clock className="w-4 h-4 text-slate-400" />
        return (
          <div key={event.message_id || idx} className="relative group">
            {/* Timeline Dot */}
            <div className="absolute -left-[31px] top-1 p-1.5 rounded-full bg-slate-900 border border-slate-700 group-hover:border-slate-500 transition-colors">
              {icon}
            </div>

            {/* Event Content Card */}
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 group-hover:border-slate-700 transition-colors">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-semibold text-white capitalize">
                    {event.agent_name}
                  </span>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 uppercase font-mono">
                    {event.event_type}
                  </span>
                </div>

                <div className="flex items-center space-x-3 text-[11px] text-slate-500">
                  {event.confidence !== undefined && (
                    <span className="font-mono text-amber-400 font-medium">
                      {(event.confidence * 100).toFixed(0)}% conf
                    </span>
                  )}
                  <span className="font-mono">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </div>

              <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                {event.content}
              </p>

              {event.evidence_refs && event.evidence_refs.length > 0 && (
                <div className="flex items-center space-x-2 mt-3 pt-2 border-t border-slate-800/60 text-xs text-slate-400">
                  <span className="text-slate-500 text-[11px]">Cited:</span>
                  {event.evidence_refs.map((ref) => (
                    <span
                      key={ref}
                      className="px-2 py-0.5 rounded bg-slate-800 text-blue-300 border border-blue-500/20 font-mono text-[11px]"
                    >
                      {ref}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
