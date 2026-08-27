import React from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  Gavel,
  LayoutDashboard,
  FolderPlus,
  FileText,
  Scale,
  GitGraph,
  History,
  Award,
  LogOut,
  ShieldCheck,
} from 'lucide-react'
import { authApi } from '../api/client'

interface LayoutProps {
  children: React.ReactNode
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation()
  const navigate = useNavigate()
  const params = useParams<{ caseId?: string }>()
  const currentCaseId = params.caseId

  const handleLogout = () => {
    authApi.logout()
  }

  const navItems = [
    { label: 'Dashboard', icon: LayoutDashboard, path: '/' },
    { label: 'New Case', icon: FolderPlus, path: '/cases/new' },
  ]

  const caseNavItems = currentCaseId
    ? [
        { label: 'Case Overview', icon: FileText, path: `/cases/${currentCaseId}` },
        { label: 'Courtroom', icon: Scale, path: `/cases/${currentCaseId}/courtroom` },
        { label: 'Evidence Explorer', icon: ShieldCheck, path: `/cases/${currentCaseId}/evidence` },
        { label: 'Evidence Graph', icon: GitGraph, path: `/cases/${currentCaseId}/graph` },
        { label: 'Trial Replay', icon: History, path: `/cases/${currentCaseId}/replay` },
        { label: 'Verdict', icon: Award, path: `/cases/${currentCaseId}/verdict` },
      ]
    : []

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between">
        <div>
          {/* Logo Header */}
          <div className="p-6 border-b border-slate-800 flex items-center space-x-3">
            <div className="p-2 bg-amber-500/10 text-amber-400 rounded-lg border border-amber-500/20">
              <Gavel className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight tracking-wide text-white">AI Courtroom</h1>
              <p className="text-xs text-slate-400">Multi-Agent Debate</p>
            </div>
          </div>

          {/* Navigation Links */}
          <div className="p-4 space-y-6">
            <div>
              <p className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Main</p>
              <nav className="space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon
                  const active = location.pathname === item.path
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                        active
                          ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span>{item.label}</span>
                    </Link>
                  )
                })}
              </nav>
            </div>

            {currentCaseId && (
              <div>
                <p className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Active Case</p>
                <nav className="space-y-1">
                  {caseNavItems.map((item) => {
                    const Icon = item.icon
                    const active = location.pathname === item.path
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                          active
                            ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        <span>{item.label}</span>
                      </Link>
                    )
                  })}
                </nav>
              </div>
            )}
          </div>
        </div>

        {/* Footer info & Logout */}
        <div className="p-4 border-t border-slate-800 space-y-3">
          <div className="bg-slate-800/50 p-2.5 rounded-md border border-slate-700/50 text-xs text-slate-400">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 mr-2"></span>
            Integration Mock Mode
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium text-red-400 hover:bg-red-950/30 hover:border-red-800/40 border border-transparent transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <header className="h-16 border-b border-slate-800 bg-slate-900/50 px-8 flex items-center justify-between backdrop-blur sticky top-0 z-10">
          <div className="flex items-center space-x-4">
            <span className="text-xs font-semibold px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
              MEMBER E UI / API LAYER
            </span>
          </div>
          <div className="text-xs text-slate-400">
            Educational & Research Simulation
          </div>
        </header>

        <div className="p-8 max-w-7xl mx-auto w-full">
          {children}
        </div>
      </main>
    </div>
  )
}
