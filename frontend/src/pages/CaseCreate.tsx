import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, Search, Sparkles, AlertCircle, CheckCircle2 } from 'lucide-react'
import { casesApi, documentsApi } from '../api/client'

export const CaseCreate: React.FC = () => {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'upload' | 'search' | 'synthetic'>('upload')

  // Form State
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Public Search State
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searchStatus, setSearchStatus] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)

  // Mode A: Upload & Create
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const newCase = await casesApi.create(title, description, 'USER_PROVIDED')
      if (file) {
        await documentsApi.upload(newCase.case_id, file)
      }
      navigate(`/cases/${newCase.case_id}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create case.')
    } finally {
      setLoading(false)
    }
  }

  // Mode B: Public Search
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setSearching(true)
    setSearchStatus(null)
    setSearchResults([])
    try {
      const res = await casesApi.searchPublic(searchQuery)
      if (res.insufficient_public_data || !res.results || res.results.length === 0) {
        setSearchStatus('insufficient_public_data')
      } else {
        setSearchResults(res.results)
      }
    } catch {
      setSearchStatus('insufficient_public_data')
    } finally {
      setSearching(false)
    }
  }

  const handleSelectPublicResult = async (item: any) => {
    setLoading(true)
    try {
      const caseTitle = item.case_name || item.title || 'Public Legal Case'
      const caseDesc = item.snippet || `Acquired from public records: ${item.court || item.collection || ''}`
      const newCase = await casesApi.create(caseTitle, caseDesc, 'PUBLIC_LEGAL_SOURCE')
      navigate(`/cases/${newCase.case_id}`)
    } catch (err: any) {
      setError('Failed to import public case.')
    } finally {
      setLoading(false)
    }
  }

  // Mode C: Synthetic benchmark picker
  const handleSelectSynthetic = async (preset: { title: string; desc: string }) => {
    setLoading(true)
    try {
      const newCase = await casesApi.create(preset.title, preset.desc, 'SYNTHETIC')
      navigate(`/cases/${newCase.case_id}`)
    } catch {
      setError('Failed to create synthetic case.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Create New Case</h2>
        <p className="text-sm text-slate-400 mt-1">
          Select an ingestion method to initiate the legal dispute simulation.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 space-x-6">
        <button
          onClick={() => setActiveTab('upload')}
          className={`flex items-center space-x-2 pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'upload'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Upload className="w-4 h-4" />
          <span>Upload Documents (Mode A)</span>
        </button>

        <button
          onClick={() => setActiveTab('search')}
          className={`flex items-center space-x-2 pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'search'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Search className="w-4 h-4" />
          <span>Public Search (Mode B)</span>
        </button>

        <button
          onClick={() => setActiveTab('synthetic')}
          className={`flex items-center space-x-2 pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'synthetic'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>Synthetic Benchmark (Mode C)</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/60 flex items-start space-x-3 text-red-300 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* TAB 1: Mode A (Upload) */}
      {activeTab === 'upload' && (
        <form onSubmit={handleUploadSubmit} className="space-y-6 bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Case Title
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Alice Corp v. Bob Ltd (Breach of Contract)"
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Dispute Summary / Description
              </label>
              <textarea
                rows={4}
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Briefly state the primary claims, parties involved, and disputed facts..."
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Upload Primary Document (PDF / DOCX / TXT)
              </label>
              <input
                type="file"
                accept=".pdf,.txt,.docx,.doc"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-600/20 file:text-blue-300 hover:file:bg-blue-600/30 file:cursor-pointer"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm transition-colors disabled:opacity-50"
          >
            {loading ? 'Creating & Ingesting...' : 'Create Case & Proceed'}
          </button>
        </form>
      )}

      {/* TAB 2: Mode B (Public Search) */}
      {activeTab === 'search' && (
        <div className="space-y-6 bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <form onSubmit={handleSearch} className="flex space-x-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search legal precedents by name, citation, or topic (e.g. 'force majeure breach')..."
              className="flex-1 px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
            />
            <button
              type="submit"
              disabled={searching}
              className="px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm transition-colors disabled:opacity-50 flex items-center space-x-2"
            >
              <Search className="w-4 h-4" />
              <span>{searching ? 'Searching...' : 'Search'}</span>
            </button>
          </form>

          {searchStatus === 'insufficient_public_data' && (
            <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700 text-slate-300 text-sm">
              <span className="font-semibold block mb-1">insufficient_public_data: true</span>
              No verified public legal records found for query "{searchQuery}". Per integration guidelines, no fake cases were fabricated. Try another query or use Mode A/C.
            </div>
          )}

          {searchResults.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase text-slate-400">Search Results</h4>
              {searchResults.map((r, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl border border-slate-800 bg-slate-950/60 flex items-center justify-between"
                >
                  <div className="space-y-1 max-w-xl">
                    <h5 className="font-semibold text-sm text-white">{r.case_name || r.title}</h5>
                    <p className="text-xs text-slate-400 line-clamp-2">{r.snippet}</p>
                    <span className="text-[11px] text-slate-500 font-mono">{r.court || r.collection}</span>
                  </div>
                  <button
                    onClick={() => handleSelectPublicResult(r)}
                    disabled={loading}
                    className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
                  >
                    Import Case
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Mode C (Synthetic Benchmark) */}
      {activeTab === 'synthetic' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            {
              title: 'Case 001: Commercial Delivery Breach',
              desc: 'Dispute over delayed software deliverable where specification changes are alleged as force majeure.',
            },
            {
              title: 'Case 002: Intellectual Property Licensing',
              desc: 'Allegation of patent infringement and breach of open source sublicensing terms.',
            },
            {
              title: 'Case 003: Non-Disclosure Agreement Violation',
              desc: 'Dispute involving alleged disclosure of proprietary trade secrets to a competitor.',
            },
          ].map((preset, idx) => (
            <div
              key={idx}
              className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 hover:border-slate-700 transition-colors flex flex-col justify-between space-y-4"
            >
              <div>
                <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 mb-2 inline-block">
                  BENCHMARK
                </span>
                <h4 className="font-semibold text-white text-sm">{preset.title}</h4>
                <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{preset.desc}</p>
              </div>

              <button
                onClick={() => handleSelectSynthetic(preset)}
                disabled={loading}
                className="w-full py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium transition-colors"
              >
                Load Benchmark
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
