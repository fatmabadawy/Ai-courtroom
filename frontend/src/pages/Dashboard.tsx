import React from 'react'
import { Link } from 'react-router-dom'
import { FolderPlus, Scale, FileText, ArrowRight, Clock, ShieldCheck } from 'lucide-react'
import { useCases } from '../hooks/useCase'

export const Dashboard: React.FC = () => {
  const { data: cases, isLoading, error } = useCases()

  return (
    <div className="space-y-8">
      {/* Header Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Legal Cases</h2>
          <p className="text-sm text-slate-400 mt-1">
            Manage legal disputes and run multi-agent courtroom trials
          </p>
        </div>
        <Link
          to="/cases/new"
          className="flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm transition-colors shadow-sm"
        >
          <FolderPlus className="w-4 h-4" />
          <span>New Case</span>
        </Link>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 flex items-center space-x-4">
          <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <span className="text-2xl font-bold text-white">{cases ? cases.length : 0}</span>
            <p className="text-xs text-slate-400">Total Cases</p>
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 flex items-center space-x-4">
          <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Scale className="w-6 h-6" />
          </div>
          <div>
            <span className="text-2xl font-bold text-white">
              {cases ? cases.filter((c) => c.status === 'completed').length : 0}
            </span>
            <p className="text-xs text-slate-400">Trials Completed</p>
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 flex items-center space-x-4">
          <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <span className="text-2xl font-bold text-white">7 Agents</span>
            <p className="text-xs text-slate-400">Debate Engine Online</p>
          </div>
        </div>
      </div>

      {/* Case List */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Your Cases</h3>

        {isLoading ? (
          <div className="p-12 text-center text-slate-400">Loading cases...</div>
        ) : error ? (
          <div className="p-6 rounded-xl bg-red-950/30 border border-red-800 text-red-300 text-sm">
            Failed to load cases. Please verify your connection.
          </div>
        ) : !cases || cases.length === 0 ? (
          <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-900/40 space-y-4">
            <Scale className="w-10 h-10 text-slate-600 mx-auto" />
            <h4 className="font-semibold text-white">No cases created yet</h4>
            <p className="text-sm text-slate-400 max-w-sm mx-auto">
              Create your first case by uploading documents, selecting a synthetic benchmark, or searching public cases.
            </p>
            <Link
              to="/cases/new"
              className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors"
            >
              <FolderPlus className="w-3.5 h-3.5" />
              <span>Create Case</span>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {cases.map((c) => (
              <div
                key={c.case_id}
                className="p-5 rounded-xl border border-slate-800 bg-slate-900/70 hover:border-slate-700 transition-colors flex items-center justify-between group"
              >
                <div className="space-y-1.5 max-w-2xl">
                  <div className="flex items-center space-x-3">
                    <h4 className="font-semibold text-base text-white group-hover:text-blue-400 transition-colors">
                      {c.title}
                    </h4>
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                      {c.provenance_type}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        c.status === 'completed'
                          ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30'
                          : c.status === 'running'
                          ? 'bg-blue-950/40 text-blue-300 border border-blue-500/30'
                          : 'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}
                    >
                      {c.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 line-clamp-1">{c.description}</p>
                  <div className="flex items-center space-x-4 text-xs text-slate-500 pt-1">
                    <span className="flex items-center space-x-1">
                      <Clock className="w-3 h-3" />
                      <span>{new Date(c.created_at).toLocaleDateString()}</span>
                    </span>
                    <span className="font-mono text-[11px]">ID: {c.case_id.slice(0, 8)}...</span>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <Link
                    to={`/cases/${c.case_id}`}
                    className="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors"
                  >
                    <span>View Overview</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                  <Link
                    to={`/cases/${c.case_id}/courtroom`}
                    className="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 text-xs font-medium transition-colors"
                  >
                    <Scale className="w-3.5 h-3.5" />
                    <span>Courtroom</span>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
