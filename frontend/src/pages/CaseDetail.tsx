import React, { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { Scale, Upload, FileText, Play, CheckCircle2, ShieldCheck, Clock } from 'lucide-react'
import { useCase } from '../hooks/useCase'
import { documentsApi, trialApi } from '../api/client'
import { useQuery, useMutation, useQueryClient } from '../shims/reactQuery'

export const CaseDetail: React.FC = () => {
  const { caseId = '' } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: currentCase, isLoading: caseLoading } = useCase(caseId)
  const { data: documents, isLoading: docsLoading } = useQuery({
    queryKey: ['documents', caseId],
    queryFn: () => documentsApi.list(caseId),
    enabled: !!caseId,
  })

  const [uploading, setUploading] = useState(false)
  const [judgeProfile, setJudgeProfile] = useState<'strict' | 'balanced' | 'skeptical'>('balanced')
  const [trialStarting, setTrialStarting] = useState(false)

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await documentsApi.upload(caseId, file)
      queryClient.invalidateQueries({ queryKey: ['documents', caseId] })
    } catch {
      alert('Failed to upload document.')
    } finally {
      setUploading(false)
    }
  }

  const handleStartTrial = async () => {
    setTrialStarting(true)
    try {
      await trialApi.start(caseId, judgeProfile)
      navigate(`/cases/${caseId}/courtroom`)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to start trial.')
    } finally {
      setTrialStarting(false)
    }
  }

  if (caseLoading) {
    return <div className="p-12 text-center text-slate-400">Loading case details...</div>
  }

  if (!currentCase) {
    return <div className="p-12 text-center text-red-400">Case not found.</div>
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <h2 className="text-2xl font-bold text-white tracking-tight">{currentCase.title}</h2>
            <span className="text-xs px-2.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-mono">
              {currentCase.provenance_type}
            </span>
          </div>
          <p className="text-xs text-slate-500 font-mono">Case ID: {currentCase.case_id}</p>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            to={`/cases/${caseId}/courtroom`}
            className="flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm transition-colors shadow-sm"
          >
            <Scale className="w-4 h-4" />
            <span>Open Courtroom</span>
          </Link>
        </div>
      </div>

      {/* Case Overview & Trial Launch Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Summary & Documents */}
        <div className="lg:col-span-2 space-y-6">
          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Dispute Summary</h3>
            <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{currentCase.description}</p>
          </div>

          {/* Documents Section */}
          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Case Documents ({documents ? documents.length : 0})
              </h3>
              <label className="cursor-pointer flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors">
                <Upload className="w-3.5 h-3.5" />
                <span>{uploading ? 'Uploading...' : 'Upload Document'}</span>
                <input
                  type="file"
                  className="hidden"
                  onChange={handleFileUpload}
                  disabled={uploading}
                />
              </label>
            </div>

            {docsLoading ? (
              <div className="text-xs text-slate-500">Loading documents...</div>
            ) : !documents || documents.length === 0 ? (
              <div className="p-6 text-center border border-dashed border-slate-800 rounded-xl text-xs text-slate-500">
                No documents uploaded yet. Upload evidence or filings for RAG indexing.
              </div>
            ) : (
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div
                    key={doc.document_id}
                    className="p-3 rounded-xl border border-slate-800 bg-slate-950/60 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center space-x-3">
                      <FileText className="w-4 h-4 text-blue-400" />
                      <div>
                        <span className="font-medium text-white">{doc.filename}</span>
                        <span className="text-slate-500 ml-2 font-mono">
                          {(doc.size_bytes / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-emerald-950/40 text-emerald-300 border border-emerald-500/20 font-mono text-[11px]">
                      {doc.upload_status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Start Trial Card */}
        <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/60 flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 w-fit">
              <Scale className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Launch AI Debate</h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Initiate the 7-agent debate protocol. The intake agent processes claims, prosecution and defense argue, fact-checker and quality agents score evidence, cross-examiner challenges, and the judge issues a verdict.
              </p>
            </div>

            <div className="space-y-2 pt-2">
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Judge Profile
              </label>
              <select
                value={judgeProfile}
                onChange={(e: any) => setJudgeProfile(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white text-xs focus:outline-none focus:border-blue-500"
              >
                <option value="balanced">Balanced (Evaluates both sides equally)</option>
                <option value="strict">Strict (Demands high proof burden)</option>
                <option value="skeptical">Skeptical (Deeply cross-examines claims)</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleStartTrial}
            disabled={trialStarting}
            className="w-full flex items-center justify-center space-x-2 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm transition-colors shadow-sm disabled:opacity-50"
          >
            <Play className="w-4 h-4 fill-white" />
            <span>{trialStarting ? 'Initiating Trial...' : 'Start Trial (Async 202)'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}
