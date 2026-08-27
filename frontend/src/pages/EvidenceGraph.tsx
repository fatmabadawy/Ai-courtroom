import React, { useState, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useEvidenceGraph } from '../hooks/useEvidenceGraph'
import { GitGraph, ZoomIn, ZoomOut, RotateCcw, Shield, FileText, Database, HelpCircle } from 'lucide-react'

export const EvidenceGraph: React.FC = () => {
  const { caseId = '' } = useParams<{ caseId: string }>()
  const { data: graphData, isLoading, error } = useEvidenceGraph(caseId)

  const [zoom, setZoom] = useState(1)
  const [selectedNode, setSelectedNode] = useState<any | null>(null)

  // Organize nodes by column: Claim -> Evidence -> Source -> Document
  const layout = useMemo(() => {
    if (!graphData || !graphData.nodes) return { nodesWithPos: [], edges: [] }

    const colX: Record<string, number> = {
      claim: 80,
      evidence: 380,
      source: 680,
      document: 980,
    }

    const typeCounts: Record<string, number> = {
      claim: 0,
      evidence: 0,
      source: 0,
      document: 0,
    }

    const nodesWithPos = graphData.nodes.map((n) => {
      const type = n.type || 'evidence'
      const count = typeCounts[type] || 0
      typeCounts[type] = count + 1

      const x = colX[type] ?? 380
      const y = 80 + count * 130

      return {
        ...n,
        x,
        y,
        width: 240,
        height: 80,
      }
    })

    const nodeMap = new Map(nodesWithPos.map((n) => [n.id, n]))

    const edges = graphData.edges
      .map((e) => {
        const sourceNode = nodeMap.get(e.source)
        const targetNode = nodeMap.get(e.target)
        if (!sourceNode || !targetNode) return null
        return {
          ...e,
          x1: sourceNode.x + sourceNode.width,
          y1: sourceNode.y + sourceNode.height / 2,
          x2: targetNode.x,
          y2: targetNode.y + targetNode.height / 2,
        }
      })
      .filter(Boolean)

    return { nodesWithPos, edges }
  }, [graphData])

  const nodeStyles: Record<string, { bg: string; border: string; text: string; icon: any }> = {
    claim: { bg: 'bg-amber-950/40', border: 'border-amber-500/40', text: 'text-amber-300', icon: HelpCircle },
    evidence: { bg: 'bg-blue-950/40', border: 'border-blue-500/40', text: 'text-blue-300', icon: Shield },
    source: { bg: 'bg-purple-950/40', border: 'border-purple-500/40', text: 'text-purple-300', icon: Database },
    document: { bg: 'bg-emerald-950/40', border: 'border-emerald-500/40', text: 'text-emerald-300', icon: FileText },
  }

  return (
    <div className="space-y-6">
      {/* Header & Zoom Controls */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Evidence Topology Graph</h2>
          <p className="text-sm text-slate-400 mt-1">
            Dependency pipeline: Claim → Evidence → Source → Document
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1 bg-slate-900 border border-slate-800 rounded-xl p-1">
            <button
              onClick={() => setZoom((z) => Math.min(z + 0.15, 1.8))}
              className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-300 transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <span className="text-xs font-mono px-2 text-slate-400">{(zoom * 100).toFixed(0)}%</span>
            <button
              onClick={() => setZoom((z) => Math.max(z - 0.15, 0.5))}
              className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-300 transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button
              onClick={() => setZoom(1)}
              className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-300 transition-colors"
              title="Reset View"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs bg-slate-900/60 p-3 rounded-xl border border-slate-800">
        <span className="text-slate-500 font-semibold uppercase tracking-wider text-[11px]">Nodes:</span>
        <span className="flex items-center space-x-1.5 text-amber-300">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400"></span>
          <span>Claim (Disputed Assertion)</span>
        </span>
        <span className="flex items-center space-x-1.5 text-blue-300">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-400"></span>
          <span>Evidence (Retrieved Content)</span>
        </span>
        <span className="flex items-center space-x-1.5 text-purple-300">
          <span className="w-2.5 h-2.5 rounded-full bg-purple-400"></span>
          <span>Source (Citation / Origin)</span>
        </span>
        <span className="flex items-center space-x-1.5 text-emerald-300">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
          <span>Document (Raw Ingested File)</span>
        </span>
      </div>

      {isLoading ? (
        <div className="h-[600px] flex items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/60 text-slate-400">
          Loading evidence graph topology...
        </div>
      ) : error ? (
        <div className="p-6 rounded-xl bg-red-950/30 border border-red-800 text-red-300 text-sm">
          Failed to load evidence graph.
        </div>
      ) : (
        <div className="h-[650px] rounded-2xl border border-slate-800 bg-slate-950 overflow-auto shadow-inner relative p-4">
          <div
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'top left',
              minWidth: 1300,
              minHeight: 700,
              position: 'relative',
            }}
          >
            {/* SVG Connecting Edges */}
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none"
              style={{ minWidth: 1300, minHeight: 700 }}
            >
              <defs>
                <marker
                  id="arrow"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
                </marker>
              </defs>
              {layout.edges.map((e: any) => {
                const dx = e.x2 - e.x1
                const cx1 = e.x1 + dx * 0.5
                const cy1 = e.y1
                const cx2 = e.x1 + dx * 0.5
                const cy2 = e.y2
                const d = `M ${e.x1} ${e.y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${e.x2} ${e.y2}`
                return (
                  <g key={e.id}>
                    <path
                      d={d}
                      fill="none"
                      stroke="#475569"
                      strokeWidth="2"
                      strokeDasharray="4 2"
                      markerEnd="url(#arrow)"
                    />
                    {e.label && (
                      <text
                        x={(e.x1 + e.x2) / 2}
                        y={(e.y1 + e.y2) / 2 - 8}
                        fill="#94a3b8"
                        fontSize="10"
                        fontFamily="monospace"
                        textAnchor="middle"
                      >
                        {e.label}
                      </text>
                    )}
                  </g>
                )
              })}
            </svg>

            {/* Render Nodes */}
            {layout.nodesWithPos.map((n: any) => {
              const style = nodeStyles[n.type] || nodeStyles.evidence
              const Icon = style.icon
              const isSelected = selectedNode?.id === n.id

              return (
                <div
                  key={n.id}
                  onClick={() => setSelectedNode(n)}
                  style={{
                    position: 'absolute',
                    left: n.x,
                    top: n.y,
                    width: n.width,
                  }}
                  className={`p-3 rounded-xl border ${style.bg} ${style.border} ${
                    isSelected ? 'ring-2 ring-blue-400 shadow-lg' : ''
                  } cursor-pointer transition-all hover:scale-[1.02] shadow-sm`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center space-x-1.5">
                      <Icon className={`w-3.5 h-3.5 ${style.text}`} />
                      <span className={`text-[11px] font-bold uppercase tracking-wider font-mono ${style.text}`}>
                        {n.type}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-900/80 px-1.5 py-0.5 rounded border border-slate-700">
                      {n.id}
                    </span>
                  </div>
                  <p className="text-xs text-white line-clamp-2 leading-relaxed font-sans">{n.label}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Selected Node Details Drawer */}
      {selectedNode && (
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80 space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Selected Node: <span className="text-white font-mono">{selectedNode.id}</span>
            </h4>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-xs text-slate-400 hover:text-white"
            >
              Close
            </button>
          </div>
          <p className="text-sm text-slate-100">{selectedNode.label}</p>
          {selectedNode.data && (
            <div className="text-xs font-mono text-slate-400 pt-1">
              Metadata: {JSON.stringify(selectedNode.data)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
