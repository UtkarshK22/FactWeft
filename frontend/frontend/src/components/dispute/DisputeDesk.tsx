import { useEffect, useState } from "react"
import { useAppStore } from "../../store/useStore"
import type { MemoryDetail } from "../../types/api"

export interface DisputeCardProps {
  memoryId: string
  title: string
  predicate: string
  objectValue: string | null
  summary: string | null
  authority: number | null
  publishedAt: number | null
  validFrom: number | null
  proposingAgent: string | null
  confidence: number | null
  evidence: Array<{ id: string; title: string; authority: number | null }>
  onSelect: (memoryId: string) => void
  onReview: (memoryId: string, reasonCode: string) => void
}

export const DisputeCard: React.FC<DisputeCardProps> = ({
  memoryId,
  title,
  predicate,
  objectValue,
  summary,
  authority,
  publishedAt,
  validFrom,
  proposingAgent,
  confidence,
  evidence,
  onReview,
}) => {
  const [reviewing] = useState(false)

  return (
    <div className="border-b border-slate-700 pb-6 last:border-0 last:pb-0">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="font-medium text-slate-200">{title}</span>
          <span className="text-xs font-semibold rounded-md px-2 py-0.5"
            style={{
              background: authority ? `hsl(${authority * 120}, 70%, 55%)` : "hsl(0, 0%, 55%)",
              color: "white",
            }}>
            {authority ? authority >= 0.75 ? "High" : authority >= 0.5 ? "Medium" : "Low" : "—"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">{new Date(publishedAt ?? 0).toLocaleDateString()}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2 mb-3">
        <div className="bg-slate-800 rounded-lg p-3">
          <p className="text-slate-300 text-sm line-clamp-3">{summary || "No summary"}</p>
        </div>

        <div className="bg-slate-800 rounded-lg p-3">
          <p className="text-slate-300 text-sm"><strong>Predicate:</strong> {predicate}</p>
          {objectValue !== null && <p className="text-slate-300 text-sm"><strong>Claim:</strong> {objectValue}</p>}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-slate-300 text-sm">
        <div>
          <p className="font-medium">Authority</p>
          <p>{confidence?.toFixed(2) ?? "—"}</p>
        </div>
        <div>
          <p className="font-medium">Valid from</p>
          <p>{new Date(validFrom ?? 0).toLocaleDateString()}</p>
        </div>
        <div>
          <p className="font-medium">Proposer</p>
          <p>{proposingAgent || "—"}</p>
        </div>
      </div>

      {evidence.length > 0 && (
        <div className="mt-3 p-3 bg-slate-800 rounded-lg">
          <p className="font-medium text-slate-400 text-xs">Sources</p>
          <div className="grid grid-cols-2 gap-1 mt-1">
            {evidence.map((ev, i) => (
              <div key={i} className="bg-slate-700 rounded px-2 py-1 text-caption">
                {ev.title || `Source ${i + 1}`}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 flex gap-2">
        <button
          onClick={() => onReview(memoryId, "superseded_by_newer_supported_claim")}
          className="flex-1 py-2 px-3 text-xs font-medium rounded-md bg-slate-800 border border-slate-600 hover:border-teal-500 hover:text-teal-400 transition-colors disabled:opacity-50"
          disabled={reviewing}
          title="Supersede with evidence"
        >
          Supersede
        </button>
        <button
          onClick={() => onReview(memoryId, "contested")}
          className="flex-1 py-2 px-3 text-xs font-medium rounded-md bg-slate-800 border border-amber-500 hover:border-amber-400 hover:text-amber-100 transition-colors disabled:opacity-50"
          disabled={reviewing}
          title="Mark as contested"
        >
          Contested
        </button>
      </div>
    </div>
  )
}

export const DisputeDesk: React.FC = () => {
  const [memoryA, setMemoryA] = useState<MemoryDetail | null>(null)
  const [memoryB, setMemoryB] = useState<MemoryDetail | null>(null)
  const [, setSharedPredicate] = useState<string | null>(null)
  const { agent } = useAppStore()
  const { asOfMs, filters } = useAppStore((s) => s.panel)
  const [concept, setConcept] = useState<string | null>(null)
  const [comparing, setComparing] = useState(false)
  const { addToast: createToast, clearToasts } = useAppStore()

  // Load memories based on concept filter
  useEffect(() => {
    if (!agent?.token) return
    clearToasts()
  }, [agent, asOfMs, concept, filters])

  const loadMemories = async (concept?: string | null) => {
    if (!agent?.token) return
    setComparing(true)
    try {
      const res = await fetch(`${"/api/disputes"}?concept=${concept || ""}`, {
        headers: { Authorization: `Bearer ${agent.token}` },
        credentials: "same-origin",
      })
      if (!res.ok) {
        const err = await res.json()
        createToast("Load disputes", err.detail || "Failed to load disputes", "OK", 5000)
        return
      }
      const data = await res.json()
      setMemoryA(data.memory_a ? { ...data.memory_a } as MemoryDetail : null)
      setMemoryB(data.memory_b ? { ...data.memory_b } as MemoryDetail : null)
      setSharedPredicate(data.shared_task || concept || null)
    } catch (e) {
      createToast("Load disputes", "Network error", "OK", 5000)
    } finally {
      setComparing(false)
    }
  }

  // Load initial data
  useEffect(() => {
    loadMemories(concept)
  }, [concept])

  return (
    <div className="min-h-screen p-6 bg-bg text-text">
      <h1 className="mb-6 text-2xl font-bold text-text">Dispute Desk</h1>

      <div className="mb-6 rounded-lg bg-slate-900 p-4">
        <div className="flex gap-2">
          <select
            value={concept || ""}
            onChange={(e) => {
              setConcept(e.target.value || null)
              loadMemories(e.target.value || null)
            }}
            className="rounded-md bg-slate-800 px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
            disabled={!agent?.token}
            aria-label="Filter disputes by concept"
          >
            <option value="">All concepts</option>
            <option value="release_freeze">Release Freeze</option>
            <option value="policy_change">Policy Change</option>
            <option value="deployment_window">Deployment Window</option>
          </select>
          {agent?.token && (
            <button
              onClick={() => loadMemories(undefined)}
              className="ml-2 rounded-md bg-amber-500 px-3 py-2 text-xs font-medium text-slate-950 hover:bg-amber-400 transition-colors"
              disabled={!agent?.token}
              aria-label="Refresh disputes list"
            >
              Refresh
            </button>
          )}
        </div>
      </div>

      {comparing && memoryA && memoryB && (
        <div className="mb-6 rounded-lg bg-slate-900 p-6 animate-spin" aria-live="polite">
          <p className="text-slate-400">Resolving dispute...</p>
        </div>
      )}

      {!comparing && memoryA && memoryB && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <DisputeCard
            memoryId={memoryA.id}
            title={memoryA.predicate || "Claim A"}
            predicate={memoryA.predicate || ""}
            objectValue={memoryA.object_value ?? null}
            summary={memoryA.summary ?? null}
            authority={memoryA.authority ?? null}
            publishedAt={memoryA.published_at ?? null}
            validFrom={memoryA.valid_from ?? null}
            proposingAgent={memoryA.proposing_agent ?? null}
            confidence={memoryA.confidence ?? null}
            evidence={memoryA.evidence ?? []}
            onSelect={(id) => {
              // Update zustand selection
              useAppStore.getState().setPanel({ selectedMemoryId: id })
            }}
            onReview={(id, reasonCode) => {
              if (window.confirm(`Apply resolution: ${reasonCode}?`)) {
                useAppStore.getState().setPanel({ selectedMemoryId: id })
                // Could also call review API
                createToast("Resolution pending", `Resolution ${reasonCode} applied`, "OK", 3000)
              }
            }}
          />

          <DisputeCard
            memoryId={memoryB.id}
            title={memoryB.predicate || "Claim B"}
            predicate={memoryB.predicate || ""}
            objectValue={memoryB.object_value ?? null}
            summary={memoryB.summary ?? null}
            authority={memoryB.authority ?? null}
            publishedAt={memoryB.published_at ?? null}
            validFrom={memoryB.valid_from ?? null}
            proposingAgent={memoryB.proposing_agent ?? null}
            confidence={memoryB.confidence ?? null}
            evidence={memoryB.evidence ?? []}
            onSelect={(id) => {
              useAppStore.getState().setPanel({ selectedMemoryId: id })
            }}
            onReview={(id, reasonCode) => {
              if (window.confirm(`Apply resolution: ${reasonCode}?`)) {
                useAppStore.getState().setPanel({ selectedMemoryId: id })
                createToast("Resolution pending", `Resolution ${reasonCode} applied`, "OK", 3000)
              }
            }}
          />
        </div>
      )}

      {memoryA && !memoryB && (
        <div className="mt-6 p-4 bg-slate-900 rounded-lg text-slate-400">
          <p>Select a second memory to compare, or choose a concept from the filter above.</p>
        </div>
      )}

      <div className="mt-6">
        <h2 className="text-sm font-semibold text-slate-400 mb-3">Resolution Engine</h2>
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-slate-800 rounded-lg p-3">
            <p className="font-medium text-slate-300 text-sm">Authority</p>
            <p className="text-slate-400 font-medium">{memoryA?.authority?.toFixed(2) ?? "—"}</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-3">
            <p className="font-medium text-slate-300 text-sm">Published at</p>
            <p className="text-slate-400 font-medium">
              {new Date(memoryA?.published_at ?? 0).toLocaleDateString()}
            </p>
          </div>
          <div className="bg-slate-800 rounded-lg p-3">
            <p className="font-medium text-slate-300 text-sm">Valid from</p>
            <p className="text-slate-400 font-medium">
              {new Date(memoryA?.valid_from ?? 0).toLocaleDateString()}
            </p>
          </div>
        </div>

        <div className="mt-4 p-3 bg-slate-900 rounded-lg">
          <p className="font-medium text-slate-300 text-sm">Resolution</p>
          <div className="grid grid-cols-5 gap-2">
            <button
              onClick={() => {
                if (window.confirm("Supersede with evidence?")) {
                  useAppStore.getState().setPanel({ selectedMemoryId: memoryA!.id })
                  createToast("Action", "Supersede selected", "OK", 3000)
                }
              }}
              className="flex-1 py-1 text-xs font-medium rounded-md bg-slate-800 border border-teal-500 hover:border-teal-400 hover:text-teal-100 transition-colors disabled:opacity-50"
              disabled={!memoryA || !memoryB}
              title="Supersede with evidence"
            >
              Supersede
            </button>
            <button
              onClick={() => {
                if (window.confirm("Coexist under different scope?")) {
                  createToast("Info", "Coexist under different scope selected", "OK", 3000)
                }
              }}
              className="flex-1 py-1 text-xs font-medium rounded-md bg-slate-800 border border-amber-500 hover:border-amber-400 hover:text-amber-100 transition-colors disabled:opacity-50"
              disabled={!memoryA || !memoryB}
              title="Coexist under different scope"
            >
              Coexist
            </button>
            <button
              onClick={() => {
                if (window.confirm("Reject?")) {
                  createToast("Action", "Reject selected", "OK", 3000)
                }
              }}
              className="flex-1 py-1 text-xs font-medium rounded-md bg-slate-800 border border-rose-500 hover:border-rose-400 hover:text-rose-100 transition-colors disabled:opacity-50"
              disabled={!memoryA || !memoryB}
              title="Reject"
            >
              Reject
            </button>
            <button
              onClick={() => {
                if (window.confirm("Keep contested?")) {
                  createToast("Info", "Keep contested selected", "OK", 3000)
                }
              }}
              className="flex-1 py-1 text-xs font-medium rounded-md bg-slate-800 border border-slate-600 hover:border-slate-400 hover:text-slate-200 transition-colors disabled:opacity-50"
              disabled={!memoryA || !memoryB}
              title="Keep contested"
            >
              Keep
            </button>
          </div>

          <div className="mt-3 p-3 bg-slate-900 rounded-lg hidden" id="decision-receipt">
            <p className="font-medium text-slate-300 text-sm">Decision receipt</p>
            <p className="mt-1 text-slate-400">Resolution applied successfully</p>
          </div>
        </div>
      </div>
    </div>
  )
}