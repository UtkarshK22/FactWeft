import { useEffect, useState } from "react"
import { useAppStore } from "../../store/useStore"


export interface HandoffSummary {
  handoff_id: string
  created_at: number | null
  scope: string | null
  policy_version: string | null
  included_memories: Array<{ id: string; summary: string | null }>
}

export interface HandoffDetails {
  handoff_id: string
  sender: string
  receiver: string
  task: string
  predicate: string
  object_value: string | null
  summary: string | null
  confidence: number | null
  valid_from: number | null
  valid_until: number | null
  cardinality: string | null
  scope: string | null
  policy_version: string | null
  created_at: number | null
  includes: Array<{ memory_id: string; summary: string | null; authority: number | null }>
  excludes: Array<{ memory_id: string; reason_code: string }>
  caveats: Array<{ memory_id: string; reason_code: string }>
  readiness: {
    verdict: "ready" | "not_ready" | "unknown"
    steps: Array<{ step: string; expected: string | null; actual: string | null; state: "completed" | "pending" | "failed"; memory_id: string | null }>
  }
  token_estimate: number
  token_budget: number
}

export const HandoffCapsule: React.FC = () => {
  const [handoffs, setHandoffs] = useState<Array<HandoffSummary>>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedHandoff, setSelectedHandoff] = useState<HandoffDetails | null>(null)
  const [comparing, setComparing] = useState(false)
  const [diffPickerActive, setDiffPickerActive] = useState(false)
  const [diffA, setDiffA] = useState<string | null>(null)
  const [diffB, setDiffB] = useState<string | null>(null)
  const { agent } = useAppStore()
  const { asOfMs } = useAppStore((s) => s.panel)
  const { addToast: createToast, clearToasts } = useAppStore()

  useEffect(() => {
    if (!agent?.token) return
    clearToasts()
    fetchHandoffs()
  }, [agent, asOfMs])

  const fetchHandoffs = async () => {
    if (!agent?.token) return
    try {
      const res = await fetch("/api/handoffs", {
        headers: { Authorization: `Bearer ${agent.token}` },
        credentials: "same-origin",
      })
      if (!res.ok) {
        const err = await res.json()
        createToast("Load handoffs", err.detail || "Failed to load handoffs", "OK", 5000)
        return
      }
      const data = await res.json()
      setHandoffs(data)
    } catch (e) {
      createToast("Load handoffs", "Network error", "OK", 5000)
    }
  }

  const loadHandoff = async (id: string) => {
    if (!agent?.token) return
    try {
      const res = await fetch(`/api/handoffs/${id}`, {
        headers: { Authorization: `Bearer ${agent.token}` },
        credentials: "same-origin",
      })
      if (!res.ok) {
        const err = await res.json()
        createToast("Load handoff", err.detail || "Failed to load handoff", "OK", 5000)
        return
      }
      const data = await res.json()
      setSelectedHandoff(data as HandoffDetails)
      setSelectedId(id)
    } catch (e) {
      createToast("Load handoff", "Network error", "OK", 5000)
    }
  }



  const loadDiff = async () => {
    if (!diffA || !diffB || !agent?.token) return
    setComparing(true)
    try {
      const res = await fetch("/api/handoffs/diff?a=" + diffA + "&b=" + diffB, {
        headers: { Authorization: `Bearer ${agent.token}` },
        credentials: "same-origin",
      })
      if (!res.ok) {
        const err = await res.json()
        createToast("Diff failed", err.detail || "Failed to compute diff", "OK", 5000)
      }
    } catch (e) {
      createToast("Diff failed", "Network error", "OK", 5000)
    } finally {
      setComparing(false)
    }
  }

  const exportJson = () => {
    if (!selectedHandoff) return
    const blob = new Blob([JSON.stringify(selectedHandoff, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `handoff-${selectedHandoff.handoff_id}.json`
    a.click()
    URL.revokeObjectURL(url)
    createToast("Exported", "Handoff JSON exported", "OK", 3000)
  }

  if (!agent?.token) {
    return (
      <div className="min-h-screen p-6 bg-bg text-text">
        <h1 className="mb-4 text-2xl font-bold text-text">Handoff Capsule</h1>
        <p className="text-slate-500 mb-6">Sign in to view handoffs</p>
        <button
          onClick={() => {
            // In a real app, this would trigger auth flow
            createToast("Auth", "Sign in required", "OK", 3000)
          }}
          className="rounded-md bg-teal-600 px-4 py-2 text-white hover:bg-teal-500 transition-colors"
        >
          Sign in with Agent
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-6 bg-bg text-text">
      <h1 className="mb-4 text-2xl font-bold text-text">Handoff Capsule</h1>

      {/* Handoff list sidebar */}
      <div className="mb-6">
        <p className="text-sm font-semibold text-slate-400 mb-2">Handoffs</p>
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {handoffs.map((h) => (
            <div
              key={h.handoff_id}
              onClick={() => loadHandoff(h.handoff_id)}
              className={selectedId === h.handoff_id
                ? "bg-slate-800 rounded-lg p-3 border border-teal-500"
                : "bg-slate-900 rounded-lg p-3 border border-slate-600 hover:border-slate-500 transition-colors cursor-pointer"}
            >
              <div className="font-medium text-slate-200">{h.handoff_id.substring(0, 8)}...</div>
              <div className="text-xs text-slate-400">
                Scope: {h.scope || "—"} | Policy: {h.policy_version || "—"} | Created: {h.created_at ? new Date(h.created_at).toLocaleDateString() : "—"}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Selected handoff details */}
      {selectedHandoff && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Capsule card */}
          <div className="rounded-lg bg-slate-900 p-5 border border-slate-700">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold rounded-md px-2 py-0.5"
                  style={{ background: "hsl(260, 60%, 50%)", color: "white" }}>
                  {agent?.agent_id?.substring(0, 2) || "US"}
                </span>
                <span className="text-slate-400 text-xs">→</span>
                <span className="text-xs font-semibold rounded-md px-2 py-0.5"
                  style={{ background: "hsl(260, 60%, 50%)", color: "white" }}>
                  {selectedHandoff.receiver.substring(0, 2) || "THEM"}
                </span>
              </div>
              <span className="text-xs text-slate-500">{selectedHandoff.task || "—"}</span>
            </div>

            {/* Task / token estimate bar */}
            <div className="mt-3 flex items-center gap-3">
              <span className="text-xs text-slate-400">Token estimate:</span>
              <span className="font-medium text-teal-400">
                {selectedHandoff.token_estimate || 0}
              </span>
              <span className="text-xs text-slate-500">/</span>
              <span className="font-medium text-amber-400">
                {selectedHandoff.token_budget || 0}
              </span>
            </div>

            {/* Included/Excluded tabs */}
            <div className="mt-4 flex rounded border-slate-600">
              <button
                onClick={() => setSelectedHandoff(prev => prev ? { ...prev, includes: [], excludes: prev.excludes } : prev)}
                className={selectedHandoff?.includes?.length > 0 ? "border-b-2 border-teal-500 text-teal-400" : "text-slate-400"}
                aria-pressed="true"
              >
                Included ({(selectedHandoff?.includes?.length || 0)})
              </button>
              <button
                onClick={() => setSelectedHandoff(prev => prev ? { ...prev, excludes: [], includes: prev.includes } : prev)}
                className={selectedHandoff?.excludes?.length > 0 ? "border-b-2 border-amber-500 text-amber-300" : "text-slate-400"}
                aria-pressed="false"
              >
                Excluded ({(selectedHandoff?.excludes?.length || 0)})
              </button>
            </div>

            {/* Included claims */}
            {(selectedHandoff?.includes?.length > 0 || selectedHandoff?.excludes?.length > 0) && (
              <div className="mt-4 space-y-3 max-h-80 overflow-y-auto">
                {selectedHandoff?.includes?.map((mem, i) => (
                  <div key={i} className="bg-slate-800 rounded-lg p-3 border border-teal-500/20">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-slate-200">{mem.summary || `Memory ${i + 1}`}</span>
                      <span className="text-xs text-teal-400">authority: {mem.authority?.toFixed(2) ?? "—"}</span>
                    </div>
                    <p className="text-slate-300 text-sm line-clamp-2 mt-1">{mem.memory_id || "—"}</p>
                  </div>
                ))}

                {selectedHandoff?.excludes?.map((ex, i) => (
                  <div key={i} className="bg-slate-800 rounded-lg p-3 border border-amber-500/20">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-slate-200">{ex.reason_code}</span>
                      <span className="text-xs text-amber-400">({i + 1} of {selectedHandoff?.excludes?.length})</span>
                    </div>
                    <p className="text-slate-300 text-sm line-clamp-1 mt-1">No content (reason: {ex.reason_code})</p>
                  </div>
                ))}
              </div>
            )}

            {/* Caveats */}
            {selectedHandoff?.caveats?.length > 0 && (
              <div className="mt-4 p-3 bg-slate-800 rounded-lg">
                <p className="font-medium text-slate-300 text-sm">Caveats</p>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {selectedHandoff.caveats.map((c, i) => (
                    <div key={i} className="bg-slate-700 rounded px-2 py-1 text-caption">
                      {c.reason_code}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Readiness checklist */}
            <div className="mt-4">
              <p className="font-medium text-slate-300 text-sm">Readiness</p>
              <div className="grid grid-cols-3 gap-2 mt-3">
                {selectedHandoff?.readiness?.steps?.map((step, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full"
                      style={{
                        background: step.state === "completed" ? "#14b8a6" : step.state === "failed" ? "#f59e0b" : "#64748b",
                      }}
                    />
                    <span className="text-xs text-slate-400 font-medium">{step.step}</span>
                    <span className="text-xs text-slate-500">{step.actual || step.expected || "—"}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Proof Path mini-graph */}
            <div className="mt-4 p-3 bg-slate-800 rounded-lg">
              <p className="font-medium text-slate-300 text-sm">Proof Path</p>
              <div className="mt-2 flex gap-2">
                <span className="w-3 h-3 rounded-full bg-teal-500 tooltip" title="Source"></span>
                <span className="w-3 h-3 rounded-full bg-amber-500 tooltip" title="Claim"></span>
                <span className="w-3 h-3 rounded-full bg-violet-500 tooltip" title="Decision"></span>
                <span className="w-3 h-3 rounded-full bg-rose-500 tooltip" title="Answer"></span>
              </div>
              <span className="text-xs text-slate-500 mt-1">Source → Claim → Decision → Answer</span>
            </div>

            {/* Diff with previous handoff */}
            <div className="mt-4">
              <p className="font-medium text-slate-300 text-sm">Diff with previous handoff</p>
              <button
                onClick={() => {
                  setDiffPickerActive(true)
                  createToast("Diff", "Select two handoffs to compare", "OK", 3000)
                }}
                className="mt-2 rounded-md bg-slate-800 px-3 py-2 text-xs font-medium text-teal-400 hover:bg-slate-700 transition-colors"
                disabled={handoffs.length < 2}
                title="Compare handoffs"
              >
                Compare
              </button>
              {diffPickerActive && (
                <div className="mt-3 space-y-3 max-h-40 overflow-y-auto">
                  <select
                    onChange={(e) => setDiffA(e.target.value)}
                    value={diffA || ""}
                    className="rounded-md bg-slate-800 px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
                    disabled={handoffs.length < 2}
                  >
                    <option value="">Select first handoff</option>
                    {handoffs.map((h) => (
                      <option key={h.handoff_id} value={h.handoff_id}>
                        {h.handoff_id.substring(0, 8)}...
                      </option>
                    ))}
                  </select>
                  <select
                    onChange={(e) => setDiffB(e.target.value)}
                    value={diffB || ""}
                    className="rounded-md ml-2 bg-slate-800 px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
                    disabled={!diffA || handoffs.length < 2}
                  >
                    <option value="">Select second handoff</option>
                    {handoffs.map((h) => (
                      <option key={h.handoff_id} value={h.handoff_id}>
                        {h.handoff_id.substring(0, 8)}...
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => loadDiff()}
                    className="rounded-md bg-amber-500 px-3 py-2 text-xs font-medium text-slate-950 hover:bg-amber-400 transition-colors"
                    disabled={!diffA || !diffB}
                  >
                    Compute Diff
                  </button>
                </div>
              )}
            </div>

            {/* Export JSON button */}
            <div className="mt-4">
              <button
                onClick={() => exportJson()}
                className="rounded-md bg-violet-600 px-4 py-2 text-xs font-medium text-white hover:bg-violet-500 transition-colors"
                aria-label="Export handoff JSON"
              >
                Export JSON
              </button>
            </div>
          </div>
        </div>
      )}

      {/* No handoff selected */}
      {!selectedHandoff && agent?.token && (
        <div className="mt-6 p-6 bg-slate-900 rounded-lg text-slate-500 text-center">
          <p>Select a handoff from the list above to view details</p>
        </div>
      )}

      {/* Diff results */}
      {comparing && (
        <div className="mt-6 fixed inset-0 bg-black/50 backdrop-blur flex items-center justify-center z-50">
          <p className="text-slate-400">Computing diff...</p>
        </div>
      )}
    </div>
  )
}