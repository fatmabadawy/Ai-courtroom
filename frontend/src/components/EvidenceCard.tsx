import React from 'react'
import { FileText, Link2, CheckCircle, Database } from 'lucide-react'
import type { EvidenceResult } from '../types/schemas'

export interface EvidenceCardProps {
  evidence: EvidenceResult
  qualityScore?: number
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({ evidence, qualityScore }) => {
  return (
    <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 hover:border-slate-700 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
            {evidence.evidence_id}
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-mono">
            {evidence.source_type}
          </span>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="text-slate-400">Relevance:</span>
          <span className="font-mono font-semibold text-emerald-400">
            {(evidence.relevance_score * 100).toFixed(0)}%
          </span>
          {qualityScore !== undefined && (
            <>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400">Quality:</span>
              <span className="font-mono font-semibold text-amber-400">
                {(qualityScore * 100).toFixed(0)}%
              </span>
            </>
          )}
        </div>
      </div>

      <p className="text-sm text-slate-200 bg-slate-950/40 p-3 rounded-lg border border-slate-800/80 mb-3 leading-relaxed">
        {evidence.content}
      </p>

      <div className="flex items-center justify-between text-xs text-slate-500">
        <div className="flex items-center space-x-3">
          {evidence.document_id && (
            <span className="flex items-center space-x-1">
              <FileText className="w-3.5 h-3.5" />
              <span>Doc: {evidence.document_id}</span>
            </span>
          )}
          {evidence.document_page !== undefined && (
            <span>Page {evidence.document_page}</span>
          )}
        </div>
      </div>
    </div>
  )
}
