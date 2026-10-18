import { useEffect, useState } from "react"
import { useAppStore } from "../../store/useStore"
import { StatusBadge } from "../StatusBadge"
import { ScopeChip } from "../ScopeChip"
import { AuthorityMeter } from "../AuthorityMeter"
import { AgentAvatar } from "../AgentAvatar"
import { ErrorState } from "../ErrorState"


interface InspectorProps {
  memoryId: string | null
  onClose: () => void
}

export function Inspector({ memoryId, onClose }: InspectorProps) {
  const { agent } = useAppStore()
  const [memoryData, setMemoryData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadMemory = async () => {
      if (!memoryId) {
        setMemoryData(null)
        setLoading(false)
        return
      }

      setLoading(true)
      try {
        const res = await fetch("/api/memories/" + memoryId, {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${agent?.token || ""}`,
          },
        })

        if (!res.ok) {
          const err = await res.json()
          throw new Error(err.message || "Failed to load memory")
        }

        const data = await res.json()
        setMemoryData(data)
      } catch (err: any) {
        setError(err.message || "Failed to load memory")
        console.error("Memory load error:", err)
      } finally {
        setLoading(false)
      }
    }

  useEffect(() => {
    loadMemory()
  }, [memoryId, agent?.token])

  if (loading) {
    return (
      <div className="p-6 rounded-md bg-bg border border-border">
        <div className="animate-shimmer rounded-md bg-surface/50 h-64 w-full mb-4" />
        <p className="text-muted">Loading memory...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 rounded-md bg-bg border border-border">
        <ErrorState error={error} retry={loadMemory} />
      </div>
    )
  }

  if (!memoryData) {
    return (
      <div className="p-6 rounded-md bg-bg border border-border EmptyState">
        <h3 className="text-lg font-medium text-text">Memory Not Found</h3>
        <p className="text-muted">The memory you requested could not be found.</p>
        <button
          onClick={onClose}
          className="mt-2 inline-flex items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-bg hover:bg-teal-400 transition-colors"
        >
          Close
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-4 bg-bg rounded-md border border-border max-h-screen overflow-y-auto">
      {/* Memory Summary Section */}
      <div>
        <h2 className="text-lg font-semibold text-text mb-3 flex items-center gap-2">
          <StatusBadge status="active" showGlyph={false} />
          <span>Memory Details</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h3 className="text-sm font-medium text-muted mb-1">Summary</h3>
            <p className="text-text truncate line-clamp-3">{memoryData.summary || "No summary available"}</p>
          </div>

          <div>
            <h3 className="text-sm font-medium text-muted mb-1">Status</h3>
            <StatusBadge status={memoryData.status as any} showGlyph={false} />
            <span className="ml-2 text-sm text-muted">{memoryData.status || "unknown"}</span>
          </div>
        </div>

        {/* Subject/Predicate/Value Claim */}
        {memoryData.subject_key && memoryData.predicate && memoryData.object_value && (
          <div className="mt-4 p-3 rounded-md bg-surface border border-border">
            <h3 className="text-sm font-medium text-muted mb-2">Claim</h3>
            <div className="grid grid-cols-2 gap-2 text-[0.65em]">
              <div>
                <span className="text-muted">subject_key</span>
                <br />
                <span className="font-mono text-text break-all">{memoryData.subject_key}</span>
              </div>
              <div>
                <span className="text-muted">predicate</span>
                <br />
                <span className="font-mono text-text break-all">{memoryData.predicate}</span>
              </div>
              <div>
                <span className="text-muted">object_value</span>
                <br />
                <span className="font-mono text-text break-all">{memoryData.object_value}</span>
              </div>
            </div>
          </div>
        )}

        {/* Scope Chip */}
        {memoryData.scope && (
          <div className="mt-2">
            <ScopeChip label="scope" count={null} active={memoryData.scope !== null} />
          </div>
        )}

        {/* Confidence Bar */}
        {memoryData.confidence !== undefined && (
          <div className="mt-2">
            <h3 className="text-xs font-medium text-muted mb-1">Confidence</h3>
            <div className="h-2 rounded-full bg-surface border border-border overflow-hidden">
              <div
                className={`h-full rounded-full bg-${(memoryData.confidence ?? 0) > 0.5 ? "accent" : "secondary"} transition-colors ${(memoryData.confidence ?? 0) > 0.5 ? "accent" : "secondary-foreground"}`}
                style={{ width: `${memoryData.confidence * 100}%` }}
              ></div>
            </div>
            <span className={`text-[0.65em] ml-2 ${(memoryData.confidence ?? 0) > 0.5 ? "text-accent" : "text-secondary"}`}>
              {((memoryData.confidence * 100) | 0)}%
            </span>
          </div>
        )}

        {/* Valid-time Range */}
        {memoryData.valid_from !== undefined || memoryData.valid_until !== undefined && (
          <div className="mt-2 grid grid-cols-2 gap-1 text-[0.65em]">
            {memoryData.valid_from !== undefined && (
              <div>
                <span className="text-muted capitalize">From</span>
                <span className="font-mono text-truncate">{new Date(memoryData.valid_from).toLocaleDateString()}</span>
              </div>
            )}
            {memoryData.valid_until !== undefined && (
              <div>
                <span className="text-muted capitalize">Until</span>
                <span className="font-mono text-truncate">{new Date(memoryData.valid_until).toLocaleDateString()}</span>
              </div>
            )}
          </div>
        )}

        {/* Revision Number */}
        {memoryData.revision !== undefined && (
          <div className="mt-2">
            <h3 className="text-xs font-medium text-muted mb-1">Revision</h3>
            <p className="font-mono text-truncate">{memoryData.revision}</p>
          </div>
        )}

        {/* Proposed-by Agent */}
        {memoryData.proposed_by && (
          <div className="mt-2 flex items-center gap-2">
            <AgentAvatar
              agentId={memoryData.proposed_by.agent_id || "agent_unknown"}
              role={memoryData.proposed_by.role || "scout"}
              size="sm"
            />
            <div>
              <p className="text-xs text-muted">Proposed by</p>
              <p className="font-medium text-text">{memoryData.proposed_by.agent_id || "unknown"}</p>
            </div>
          </div>
        )}

        {/* Source Cards */}
        {(memoryData as any).source_cards && (memoryData as any).source_cards.length > 0 && (
          <div className="mt-3">
            <h3 className="text-xs font-medium text-muted mb-1">Sources</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1">
              {memoryData.source_cards.map((src: any, i: number) => (
                <div
                  key={i}
                  className="p-2 rounded-md bg-surface border border-border h-full"
                >
                  <div className="text-[0.6em] text-muted mb-0.5">Type: {src.type || "unknown"}</div>
                  <AuthorityMeter pips={3} active={src.authority || 1} className="mb-0.5" />
                  <p className="text-[0.6em] text-text truncate">{src.title || "Untitled"}</p>
                </div>
              ))}
            </div>
          </div>
        )}
        {(memoryData.evidence && memoryData.evidence.length > 0) && (
          <div className="mt-4">
            <h3 className="text-xs font-medium text-muted mb-2">Evidence</h3>
            <div className="space-y-1">
              {memoryData.evidence.map((ev: any, i: number) => (
                <div key={i} className="p-2 rounded-md bg-surface border border-border text-[0.65em]">
                  <p className="font-medium text-text">{ev.title || "Untitled"}</p>
                  <p className="text-muted truncate">Authority: {ev.authority ?? "—"}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

