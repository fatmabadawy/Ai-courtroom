import React from 'react'
import { Award, AlertOctagon, HelpCircle, CheckCircle2, XCircle, ShieldAlert } from 'lucide-react'
import type { Verdict } from '../types/schemas'

export interface VerdictPanelProps {
  verdict: Verdict
}

export const VerdictPanel: React.FC<VerdictPanelProps> = ({ verdict }) => {
  return (
    <div className="space-y-6">
      {/* Mandatory Disclaimer Banner */}
      <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start space-x-3">
        <AlertOctagon className="w-5 h-5 text-amber-400 mt-0.5 flex-shrink-0" />
        <div className="text-sm">
          <h4 className="font-semibold text-amber-300">Disclaimer</h4>
          <p className="text-amber-200/80 text-xs mt-0.5 leading-relaxed">
            {verdict.disclaimer}
          </p>
        </div>
      </div>

      {/* Primary Finding Card */}
      <div className="p-6 rounded-2xl border border-slate-700 bg-slate-900 shadow-lg space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Award className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-bold text-lg text-white">Court Verdict</h3>
              <p className="text-xs text-slate-400">
                Judge Profile: <span className="capitalize text-slate-200 font-medium">{verdict.judge_profile}</span>
              </p>
            </div>
          </div>

          <div className="text-right">
            <span className="text-xs text-slate-400 block mb-1">Confidence Score</span>
            <span className="text-sm font-mono font-bold px-3 py-1 rounded-lg bg-slate-800 text-amber-400 border border-slate-700">
              {(verdict.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        {/* Finding */}
        <div className="space-y-1.5">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Finding</h4>
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-base font-medium text-slate-100 leading-relaxed">
            {verdict.finding}
          </div>
        </div>

        {/* Legal Reasoning */}
        <div className="space-y-1.5">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Judicial Reasoning</h4>
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
            {verdict.reasoning}
          </div>
        </div>
      </div>

      {/* Supporting vs Opposing Evidence & Unresolved Questions Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Supporting Evidence */}
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3">
          <div className="flex items-center space-x-2 text-emerald-400 font-semibold text-sm">
            <CheckCircle2 className="w-4 h-4" />
            <h4>Supporting Evidence ({verdict.supporting_evidence_ids.length})</h4>
          </div>
          <div className="flex flex-wrap gap-2">
            {verdict.supporting_evidence_ids.length > 0 ? (
              verdict.supporting_evidence_ids.map((id) => (
                <span
                  key={id}
                  className="px-2.5 py-1 rounded-md bg-emerald-950/30 text-emerald-300 border border-emerald-500/20 text-xs font-mono"
                >
                  {id}
                </span>
              ))
            ) : (
              <span className="text-xs text-slate-500 italic">None cited</span>
            )}
          </div>
        </div>

        {/* Opposing Evidence */}
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3">
          <div className="flex items-center space-x-2 text-red-400 font-semibold text-sm">
            <XCircle className="w-4 h-4" />
            <h4>Opposing Evidence ({verdict.opposing_evidence_ids.length})</h4>
          </div>
          <div className="flex flex-wrap gap-2">
            {verdict.opposing_evidence_ids.length > 0 ? (
              verdict.opposing_evidence_ids.map((id) => (
                <span
                  key={id}
                  className="px-2.5 py-1 rounded-md bg-red-950/30 text-red-300 border border-red-500/20 text-xs font-mono"
                >
                  {id}
                </span>
              ))
            ) : (
              <span className="text-xs text-slate-500 italic">None cited</span>
            )}
          </div>
        </div>
      </div>

      {/* Unresolved Questions */}
      {verdict.unresolved_questions && verdict.unresolved_questions.length > 0 && (
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3">
          <div className="flex items-center space-x-2 text-blue-400 font-semibold text-sm">
            <HelpCircle className="w-4 h-4" />
            <h4>Unresolved Legal Questions</h4>
          </div>
          <ul className="space-y-2">
            {verdict.unresolved_questions.map((q, idx) => (
              <li
                key={idx}
                className="text-xs text-slate-300 bg-slate-950/40 p-3 rounded-lg border border-slate-800/80 flex items-start space-x-2"
              >
                <span className="text-slate-500 font-mono">{idx + 1}.</span>
                <span>{q}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
