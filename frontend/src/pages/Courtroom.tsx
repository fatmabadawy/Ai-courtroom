import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Scale,
  Play,
  Pause,
  RotateCcw,
  Award,
  AlertCircle,
  Clock,
  Shield,
  HelpCircle,
  CheckCircle2,
  AlertTriangle,
  UserCheck,
  Flame,
  PlusCircle,
} from 'lucide-react'
import { useTrialState } from '../hooks/useTrialState'
import { trialApi } from '../api/client'
import { AgentCard } from '../components/AgentCard'

export const Courtroom: React.FC = () => {
  const { caseId = '' } = useParams<{ caseId: string }>()
  const { data: trialState, isLoading, refetch } = useTrialState(caseId)

  const [interventionDoc, setInterventionDoc] = useState('')
  const [interventionClaim, setInterventionClaim] = useState('')
  const [intervening, setIntervening] = useState(false)
  const [resuming, setResuming] = useState(false)

  const handleIntervene = async (e: React.FormEvent) => {
    e.preventDefault()
    setIntervening(true)
    try {
      await trialApi.intervene(caseId, {
        new_document_ids: interventionDoc ? [interventionDoc] : [],
        affected_claim_ids: interventionClaim ? [interventionClaim] : [],
        submitted_at: new Date().toISOString(),
      })
      refetch()
    } catch {
      alert('Failed to submit intervention.')
    } finally {
      setIntervening(false)
    }
  }

  const handleResume = async () => {
    setResuming(true)
    try {
      await trialApi.resume(caseId)
      refetch()
    } catch {
      alert('Failed to resume trial.')
    } finally {
      setResuming(false)
    }
  }

  const snapshot = trialState?.state_snapshot || {}
  const claims = (snapshot.claims as any[]) || []
  const prosArgs = (snapshot.prosecution_arguments as any[]) || []
  const defArgs = (snapshot.defense_arguments as any[]) || []
  const factChecks = (snapshot.fact_checks as any[]) || []
  const qualityScores = (snapshot.evidence_quality as Record<string, any>) || {}
  const crossExams = (snapshot.cross_examinations as any[]) || []
  const verdict = snapshot.verdict as any

  const status = trialState?.status || 'pending'

  return (
    <div className="space-y-8">
      {/* Header and Controls */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <h2 className="text-2xl font-bold text-white tracking-tight">Courtroom Debate Floor</h2>
            <span
              className={`text-xs px-3 py-1 rounded-full font-medium ${
                status === 'completed'
                  ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30'
                  : status === 'running'
                  ? 'bg-blue-950/40 text-blue-300 border border-blue-500/30 animate-pulse'
                  : status === 'paused'
                  ? 'bg-amber-950/40 text-amber-300 border border-amber-500/30'
                  : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}
            >
              Status: {status.toUpperCase()}
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Real-time multi-agent argument exchange and fact-checking protocol
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {status === 'paused' && (
            <button
              onClick={handleResume}
              disabled={resuming}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors"
            >
              <Play className="w-3.5 h-3.5" />
              <span>{resuming ? 'Resuming...' : 'Resume Trial'}</span>
            </button>
          )}

          {status === 'completed' && (
            <Link
              to={`/cases/${caseId}/verdict`}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium transition-colors"
            >
              <Award className="w-3.5 h-3.5" />
              <span>View Full Verdict</span>
            </Link>
          )}
        </div>
      </div>

      {/* Agents Arena Grid */}
      <div className="space-y-6">
        {/* Row 1: Intake & Claims Overview */}
        {claims.length > 0 && (
          <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-3">
            <div className="flex items-center space-x-2 text-blue-400 font-semibold text-sm">
              <HelpCircle className="w-4 h-4" />
              <h3>Intake Agent — Formulated Legal Claims</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {claims.map((cl: any) => (
                <div
                  key={cl.claim_id}
                  className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1.5"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono text-slate-400">{cl.claim_id}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-mono ${
                        cl.status === 'SUPPORTED'
                          ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/20'
                          : cl.status === 'PARTIALLY_SUPPORTED'
                          ? 'bg-amber-950/40 text-amber-300 border border-amber-500/20'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {cl.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-200">{cl.statement}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Row 2: Prosecution vs Defense */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Prosecution Agent */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-red-400 flex items-center space-x-2">
              <Flame className="w-4 h-4" />
              <span>Prosecution Arguments</span>
            </h3>
            {prosArgs.length === 0 ? (
              <div className="p-6 text-center border border-slate-800 rounded-xl bg-slate-900/40 text-xs text-slate-500">
                Awaiting prosecution filings...
              </div>
            ) : (
              prosArgs.map((arg: any, i: number) => (
                <AgentCard
                  key={i}
                  name="Prosecution"
                  role="prosecution"
                  confidence={arg.confidence}
                  content={arg.argument}
                  evidenceRefs={arg.evidence_ids}
                  colorTheme="red"
                />
              ))
            )}
          </div>

          {/* Defense Agent */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-blue-400 flex items-center space-x-2">
              <Shield className="w-4 h-4" />
              <span>Defense Arguments</span>
            </h3>
            {defArgs.length === 0 ? (
              <div className="p-6 text-center border border-slate-800 rounded-xl bg-slate-900/40 text-xs text-slate-500">
                Awaiting defense response...
              </div>
            ) : (
              defArgs.map((arg: any, i: number) => (
                <AgentCard
                  key={i}
                  name="Defense"
                  role="defense"
                  confidence={arg.confidence}
                  content={arg.argument}
                  evidenceRefs={arg.evidence_ids}
                  colorTheme="blue"
                />
              ))
            )}
          </div>
        </div>

        {/* Row 3: Fact Checker & Evidence Quality */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Fact Checker */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4" />
              <span>Fact Checker Verification</span>
            </h3>
            {factChecks.length === 0 ? (
              <div className="p-6 text-center border border-slate-800 rounded-xl bg-slate-900/40 text-xs text-slate-500">
                Fact checks pending...
              </div>
            ) : (
              factChecks.map((fc: any, i: number) => (
                <AgentCard
                  key={i}
                  name="Fact Checker"
                  role="fact_checker"
                  status={fc.status}
                  confidence={fc.confidence}
                  content={fc.reasoning}
                  evidenceRefs={fc.supporting_evidence_ids}
                  colorTheme="emerald"
                />
              ))
            )}
          </div>

          {/* Cross Examiner */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-purple-400 flex items-center space-x-2">
              <Scale className="w-4 h-4" />
              <span>Cross-Examiner Challenge</span>
            </h3>
            {crossExams.length === 0 ? (
              <div className="p-6 text-center border border-slate-800 rounded-xl bg-slate-900/40 text-xs text-slate-500">
                Cross-examinations pending...
              </div>
            ) : (
              crossExams.map((cx: any, i: number) => (
                <AgentCard
                  key={i}
                  name="Cross Examiner"
                  role="cross_examiner"
                  status={`Outcome: ${cx.outcome}`}
                  content={`Question: ${cx.question}\n\nResponse: ${cx.response}`}
                  colorTheme="purple"
                />
              ))
            )}
          </div>
        </div>

        {/* Row 4: Judge Verdict Preview */}
        {verdict && (
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-amber-400 flex items-center space-x-2">
              <UserCheck className="w-4 h-4" />
              <span>Judge Ruling</span>
            </h3>
            <AgentCard
              name="Presiding Judge"
              role="judge"
              confidence={verdict.confidence}
              content={`FINDING: ${verdict.finding}\n\nREASONING: ${verdict.reasoning}`}
              evidenceRefs={verdict.supporting_evidence_ids}
              colorTheme="amber"
            />
          </div>
        )}
      </div>

      {/* Human Intervention Dock */}
      <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-4">
        <div className="flex items-center space-x-2 text-slate-300">
          <PlusCircle className="w-4 h-4 text-blue-400" />
          <h3 className="font-semibold text-sm">Human-in-the-Loop Intervention</h3>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Inject new evidence or dispute a claim during the trial. Submitting an intervention pauses the current trial round and requests agent re-evaluation.
        </p>

        <form onSubmit={handleIntervene} className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            type="text"
            value={interventionDoc}
            onChange={(e) => setInterventionDoc(e.target.value)}
            placeholder="New Document ID (e.g. DOC-NEW-1)"
            className="px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-blue-500"
          />
          <input
            type="text"
            value={interventionClaim}
            onChange={(e) => setInterventionClaim(e.target.value)}
            placeholder="Affected Claim ID (e.g. CL-001)"
            className="px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            disabled={intervening}
            className="py-2 px-4 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 text-xs font-medium transition-colors disabled:opacity-50"
          >
            {intervening ? 'Submitting...' : 'Submit Intervention'}
          </button>
        </form>
      </div>
    </div>
  )
}
