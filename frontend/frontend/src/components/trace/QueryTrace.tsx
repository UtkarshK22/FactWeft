import { useEffect, useState } from "react"
import { useAppStore } from "../../store/useStore"
import type { TraceEntryResponse, TraceResponse } from "../../types/api"

export const QueryTrace: React.FC = () => {
  const [trace, setTrace] = useState<TraceResponse | null>(null)
  const [filteredByRequestId, setFilteredByRequestId] = useState<string | null>(null)
  const { agent } = useAppStore()
  const { asOfMs } = useAppStore((s) => s.panel)
  const { addToast: createToast, clearToasts } = useAppStore()

  useEffect(() => {
    if (!agent?.token) return
    clearToasts()
    fetchTrace()
  }, [agent, asOfMs])

  const fetchTrace = async () => {
    if (!agent?.token) return
    try {
      const res = await fetch("/api/trace", {
        headers: { Authorization: `Bearer ${agent.token}` },
        credentials: "same-origin",
      })
      if (!res.ok) {
        const err = await res.json()
        createToast("Load trace", err.detail || "Failed to load trace", "OK", 5000)
        return
      }
      const data = await res.json()
      setTrace(data)
    } catch (e) {
      createToast("Load trace", "Network error", "OK", 5000)
    }
  }

  const filteredEntries = trace?.entries?.filter(
    (e: TraceEntryResponse) => !filteredByRequestId || e.request_id.includes(filteredByRequestId)
  ) || []

  return (
    <div className="min-h-screen p-6 bg-bg text-text">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="bg-slate-900 rounded-lg p-4 mb-4 border border-slate-700 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text">Query Trace</h1>
            <p className="text-slate-500 text-sm">FalkorDB powers this graph</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-md px-2 py-1 text-xs font-medium"
              style={{
                background: "hsl(43, 96%, 58%)",
                color: "rgb(30, 30, 30)",
              }}>
              {trace?.count} traces
            </span>
            <select
              value={filteredByRequestId || ""}
              onChange={(e) => setFilteredByRequestId(e.target.value || null)}
              className="rounded-md bg-slate-800 px-3 py-2 text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
              aria-label="Filter traces by request ID"
            >
              <option value="">All traces</option>
              {filteredEntries.map((e) => (
                <option key={e.request_id} value={e.request_id}>
                  {e.request_id.substring(0, 8)}...
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Trace entries list */}
        {trace && (
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {filteredEntries.map((entry, i) => (
              <div
                key={i}
                onClick={() => setFilteredByRequestId(entry.request_id)}
                className={filteredByRequestId === entry.request_id
                  ? "bg-slate-800 rounded-lg p-4 border border-teal-500"
                  : "bg-slate-900 rounded-lg p-4 border border-slate-600 hover:border-slate-500 transition-colors cursor-pointer"}
                aria-expanded={filteredByRequestId === entry.request_id ? "true" : "false"}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-2 h-2 rounded-full"
                      style={{
                        background: entry.write ? "teal-500" : "amber-500",
                        height: "2px",
                      }}
                    />
                    <span className="text-slate-300 text-sm">{entry.query_name || "—"}</span>
                    <span className="text-xs text-slate-500">{entry.duration_ms?.toFixed(1) || "—"}ms</span>
                  </div>
                  <span className="text-xs text-slate-500">{new Date(entry.ts).toLocaleTimeString()}</span>
                </div>

                {/* Request ID badge */}
                <div className="mt-2 text-xs">
                  <span className="rounded-md px-1.5 py-0.5 text-caption bg-slate-800/50 text-slate-400">
                    {entry.request_id}
                  </span>
                </div>

                {/* Expand to show Cypher and results */}
                {filteredByRequestId === entry.request_id && (
                  <div className="mt-3 pt-3 border-t border-slate-700">
                    <p className="font-medium text-slate-300 text-sm">Cypher Query</p>
                    <div className="mt-2 rounded-md bg-slate-800 p-3 overflow-x-auto">
                      <pre className="text-xs text-slate-400 overflow-auto">
                        {entry.cypher}
                        {/* Parameters would be rendered here */}
                        {JSON.stringify(entry.params, null, 2).split("\n").slice(0, 3).map((l: string, j: number) => (
                          <span key={j} className="ml-2 text-caption text-slate-500/50">{l}</span>
                        ))}
                      </pre>
                    </div>

                    <p className="mt-3 text-slate-400 text-sm">Result: {entry.rows} rows</p>

                    {/* Link to Inspector/Handoff */}
                    {entry.error ? (
                      <p className="mt-2 text-red-500 text-xs">Error: {entry.error}</p>
                    ) : (
                      <p className="mt-2">
                        <span className="font-medium text-slate-300 text-sm">
                          Produced by:
                        </span>
                        <a
                          href="#"
                          className="text-teal-400 underline underline-offset-2 hover:opacity-90 cursor-pointer"
                          title="Open related memory"
                        >
                          Memory / Handoff
                        </a>
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}

            {filteredEntries.length === 0 && !filteredByRequestId && (
              <p className="text-slate-500 text-sm pt-4">No traces yet. Perform actions to generate trace entries.</p>
            )}
          </div>
        )}

        {/* No trace data */}
        {!trace && agent?.token && (
          <div className="mt-6 p-6 bg-slate-900 rounded-lg text-slate-500 text-center">
            <p>No trace data available</p>
          </div>
        )}

        {/* No token */}
        {!agent?.token && (
          <div className="mt-6 p-6 bg-slate-900 rounded-lg text-slate-500 text-center">
            <p>Sign in to view query traces</p>
          </div>
        )}
      </div>
    </div>
  )
}