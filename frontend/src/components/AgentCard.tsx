import React from 'react'
import { Shield, Scale, HelpCircle, CheckCircle2, AlertTriangle, UserCheck, Flame } from 'lucide-react'

export interface AgentCardProps {
  name: string
  role: string
  status?: string
  confidence?: number
  content: string
  evidenceRefs?: string[]
  timestamp?: string
  colorTheme?: 'blue' | 'red' | 'amber' | 'emerald' | 'purple' | 'indigo' | 'slate'
}

const roleIcons: Record<string, React.ReactNode> = {
  intake: <HelpCircle className="w-5 h-5" />,
  prosecution: <Flame className="w-5 h-5 text-red-400" />,
  defense: <Shield className="w-5 h-5 text-blue-400" />,
  fact_checker: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
  evidence_quality: <AlertTriangle className="w-5 h-5 text-amber-400" />,
  cross_examiner: <Scale className="w-5 h-5 text-purple-400" />,
  judge: <UserCheck className="w-5 h-5 text-indigo-400" />,
}

export const AgentCard: React.FC<AgentCardProps> = ({
  name,
  role,
  status = 'active',
  confidence,
  content,
  evidenceRefs = [],
  timestamp,
  colorTheme = 'slate',
}) => {
  const borderColors: Record<string, string> = {
    blue: 'border-blue-500/30 bg-blue-950/20',
    red: 'border-red-500/30 bg-red-950/20',
    amber: 'border-amber-500/30 bg-amber-950/20',
    emerald: 'border-emerald-500/30 bg-emerald-950/20',
    purple: 'border-purple-500/30 bg-purple-950/20',
    indigo: 'border-indigo-500/30 bg-indigo-950/20',
    slate: 'border-slate-800 bg-slate-900/60',
  }

  const roleKey = role.toLowerCase().replace(/\s+/g, '_')
  const icon = roleIcons[roleKey] || <Scale className="w-5 h-5 text-slate-400" />

  return (
    <div className={`p-5 rounded-xl border ${borderColors[colorTheme] || borderColors.slate} transition-all shadow-sm`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-slate-800 border border-slate-700">
            {icon}
          </div>
          <div>
            <h4 className="font-semibold text-sm text-white capitalize">{name}</h4>
            <span className="text-xs text-slate-400 capitalize">{role} Agent</span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {confidence !== undefined && (
            <div className="text-right">
              <span className="text-xs text-slate-400 mr-1.5">Confidence</span>
              <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-slate-800 text-amber-300 border border-slate-700">
                {(confidence * 100).toFixed(0)}%
              </span>
            </div>
          )}
          {status && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
              {status}
            </span>
          )}
        </div>
      </div>

      {/* Output / Argument Content */}
      <div className="text-sm text-slate-200 leading-relaxed bg-slate-950/50 p-3.5 rounded-lg border border-slate-800/80 mb-3 whitespace-pre-wrap">
        {content}
      </div>

      {/* Evidence References and Metadata */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400 pt-2 border-t border-slate-800/60">
        <div className="flex items-center flex-wrap gap-1.5">
          <span className="font-medium text-slate-500">Evidence Cited:</span>
          {evidenceRefs && evidenceRefs.length > 0 ? (
            evidenceRefs.map((ref) => (
              <span
                key={ref}
                className="px-2 py-0.5 rounded bg-slate-800 text-blue-300 border border-blue-500/20 font-mono text-[11px]"
              >
                {ref}
              </span>
            ))
          ) : (
            <span className="text-slate-500 italic">None</span>
          )}
        </div>

        {timestamp && (
          <span className="text-slate-500 font-mono text-[11px]">
            {new Date(timestamp).toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  )
}
