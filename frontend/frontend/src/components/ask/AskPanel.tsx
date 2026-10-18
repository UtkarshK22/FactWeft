import { useEffect, useState } from "react"
import { useAppStore } from "../../store/useStore"
import { postAsk, getBearerToken, createToast, clearToasts } from "../../lib/api"
import { AskResponse, Caveat, Excluded, WhatChanged, Citation, Step, Readiness } from "../../types/api"
import { DisputeDesk } from "../dispute/DisputeDesk"
import { HandoffCapsule } from "../handoff/HandoffCapsule"

export interface SuggestedQuestion {
  id: string
  text: string
}

export const AskPanel: React.FC = () => {
  const [input, setInput] = useState("")
  const [answer, setAnswer] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [events, setEvents] = useState<Array<{ step: string; status: "pending" | "completed" | "failed"; message?: string }>>([])
  const [caveats, setCaveats] = useState<Array<Caveat>>([])
  const [excluded, setExcluded] = useState<Array<Excluded>>([])
  const [whatChanged, setWhatChanged] = useState<WhatChanged | null>(null)
  const [grounding, setGrounding] = useState<"verified citations" | "template fallback">("verified citations")
  const [showProof, setShowProof] = useState(false)
  const [handoffId, setHandoffId] = useState<string | null>(null)
  const { agent, asOfMs } = useAppStore()
  const { createToast, clearToasts } = useAppStore()

  // Suggested questions
  const suggestedQuestions: SuggestedQuestion[] = [
    { id: "1", text: "What is the status of the release freeze claim?" },
    { id: "2", text: "Compare the Oct 17 and Oct 18 claims" },
    { id: "3", text: "Is the rumour claim contested?" },
    { id: "4", text: "What changed between Session 1 and Session 2?" },
    { id: "5", text: "Show me the decision evidence" },
  ]

  // Handle question selection
  const handleSelectQuestion = (question: SuggestedQuestion) => {
    setInput(question.text)
    setAnswer(null)
    clearToasts()
    setProgress(0)
    setEvents([])
    setCaveats([])
    setExcluded([])
    setWhatChanged(null)
    setGrounding("verified citations" as "verified citations")
    setShowProof(false)
    setHandoffId(null)
  }

  // Post ask request
  const handleSubmit = async () => {
    if (!input.trim() || !agent?.token) return
    setLoading(true)
    setProgress(0)
    setEvents([])
    setCaveats([])
    setExcluded([])
    setWhatChanged(null)
    setGrounding("verified citations")
    setShowProof(false)
    setHandoffId(null)

    try {
      const res = await postAsk({ question: input.trim(), llm_mode: "fixture" })
      setAnswer(res.answer)
      setCaveats(res.caveats || [])
      setExcluded(res.excluded || [])
      setWhatChanged(res.what_changed || { added: [], removed: [], changed: [] })
      setGrounding(res.grounding || "verified citations")
      setHandoffId(res.handoff_id || null)

      // Set up event polling for progress ticker
      setupEventPolling(res.trace_ids || [])

      // Show toast for 422 abstentions
      if (res.answer?.includes("abstain") || res.answer?.includes("unable")) {
        createToast("Abstention", "The agent was unable to answer the question", "OK", 8000)
      }
    } catch (e: any) {
      // Handle 403 - agent switch demo
      if (e.message?.includes("403") || e.message?.includes("auth")) {
        createToast("Access denied", "Asking as Scout returns 403 - insufficient permissions", "OK", 5000)
        createToast("Working", "Asking as Planner works - full permissions", "OK", 5000)
      } else if (e.message?.includes("422")) {
        createToast("Unprocessable", e.message || "The request could not be processed", "OK", 5000)
      } else {
        createToast("Ask failed", e.message || "Unknown error", "OK", 5000)
      }
    } finally {
      setLoading(false)
    }
  }

  // Setup event polling for progress ticker
  useEffect(() => {
    let cancel = false

    const setupEventPolling = (traceIds: string[]) => {
      const fetchEvents = async () => {
        if (!agent?.token || cancel) return
        try {
          const res = await fetch("/api/events", {
            headers: { Authorization: `Bearer ${agent.token}` },
            credentials: "same-origin",
          })
          if (!res.ok) return
          const data = await res.json()
          setEvents(data.events || [])
          setProgress(data.progress || 0)
          // Continue polling if not complete
          if (!data.completed && !cancel) {
            setTimeout(fetchEvents, 2000)
          }
        } catch (e) {
          // Ignore polling errors
        }
      }

      // Initial fetch
      fetchEvents()
    }

    return () => {
      cancel = true
    }
  }, [agent?.token])

  // Handle show proof path
  const handleShowProof = () => {
    setShowProof(true)
    createToast("Proof path", "Opening proof path in graph", "OK", 3000)
  }

  // Handle open handoff
  const handleOpenHandoff = () => {
    if (handoffId) {
      setHandoffId(handoffId)
      createToast("Handoff", "Opening handoff capsule", "OK", 3000)
    }
  }

  return (
    <div className="min-h-screen p-6 bg-bg text-text">
      <div className="max-w-4xl mx-auto">
        {/* Command bar */}
        <div className="bg-slate-900 rounded-lg p-4 mb-6 border border-slate-700">
          <h2 className="text-lg font-bold text-text mb-3">Ask a Question</h2>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSubmit()
            }}
          >
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleSubmit()
                  }
                }}
                placeholder="Enter your question..."
                className="flex-1 rounded-md bg-slate-800 border border-slate-600 px-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 transition-colors"
                disabled={!agent?.token || loading}
                aria-label="Ask a question"
                aria-disabled={!agent?.token || loading}
              />
              <button
                type="submit"
                disabled={!agent?.token || !input.trim() || loading}
                className="rounded-md bg-teal-600 px-4 py-2 text-white font-medium hover:bg-teal-500 transition-colors"
                aria-label="Submit question"
              >
                {loading ? "Sending..." : "Ask"}
              </button>
            </div>

            {/* Suggested questions below */}
            {loading ? null : (
              <div className="mt-3 grid grid-cols-2 gap-2">
                {suggestedQuestions.map((q) => (
                  <button
                    key={q.id}
                    onClick={() => handleSelectQuestion(q)}
                    className="rounded-md bg-slate-800 px-3 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700 transition-colors cursor-pointer"
                  >
                    {q.text}
                  </button>
                ))}
              </div>
            )}
          </form>
        </div>

        {/* Progress ticker */}
        {!loading && events.length > 0 && (
          <div className="mb-4">
            <p className="text-sm font-semibold text-slate-400 mb-2">Progress</p>
            <div className="bg-slate-800 rounded-lg h-2 overflow-hidden">
              <div
                className="bg-teal-600 h-2 transition-width ease-out duration-500"
                style={{ width: progress > 0 ? progress + "%" : "0%" }}
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow={progress}
              />
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {progress}% — {events.length > 0 ? events[events.length - 1]?.step || "—" : "—"}
            </p>
          </div>
        )}

        {/* Answer section */}
        {answer && (
          <div className="mt-6 space-y-4">
            <h2 className="text-xl font-bold text-text">Answer</h2>

            {/* Grounding badge */}
            <div className="flex items-center gap-2 mb-4">
              <span className="rounded-md px-2 py-1 text-xs font-medium"
                style={{
                  background: grounding === "verified citations" ? "hsl(160, 70%, 55%)" : "hsl(0, 80%, 55%)",
                  color: "white",
                }}>
                {grounding}
              </span>
            </div>

            {/* Answer text */}
            <div className="bg-slate-900 rounded-lg p-4 mb-4 line-clamp-12">
              {answer}
            </div>

            {/* Inline citation chips */}
            {answer && /\[mem_\w+\]/.test(answer) && (
              <div className="mt-3">
                <p className="text-sm text-slate-400 mb-2">Citations</p>
                <div className="flex flex-wrap gap-2">
                  {"mem_1 mem_2 mem_3 mem_4 mem_5".split(" ").map((cid, i) => (
                    <span
                      key={cid}
                      className="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium bg-teal-500/20 text-teal-400 border border-teal-500/20"
                      onClick={() => {
                        // Select memory in graph
                        useAppStore.getState().setPanel((s: any) => ({
                          ...s,
                          panel: { ...s.panel, selectedMemoryId: cid },
                        }))
                        createToast("Selected", "Memory " + cid + " selected in graph", "OK", 3000)
                      }}
                    >
                      [{cid}]
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* What changed block */}
            {whatChanged && Object.keys(whatChanged).length > 0 && (
              <div className="mt-4 p-3 bg-slate-900 rounded-lg">
                <p className="font-medium text-slate-300 text-sm">What changed</p>
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-slate-800 rounded-lg p-2">
                    <p className="text-xs text-slate-400 font-medium">Added</p>
                    <p className="text-slate-300 text-sm line-clamp-2">
                      {whatChanged.added.length > 0
                        ? whatChanged.added.map((a) => "- " + (a.summary || a.id)).join("\n")
                        : "—"}
                    </p>
                  </div>
                  <div className="bg-slate-800 rounded-lg p-2">
                    <p className="text-xs text-slate-400 font-medium">Removed</p>
                    <p className="text-slate-300 text-sm line-clamp-2">
                      {whatChanged.removed.length > 0
                        ? whatChanged.removed.map((r) => "- " + r.reason_code).join("\n")
                        : "—"}
                    </p>
                  </div>
                  <div className="bg-slate-800 rounded-lg p-2">
                    <p className="text-xs text-slate-400 font-medium">Changed</p>
                    <p className="text-slate-300 text-sm line-clamp-2">
                      {whatChanged.changed.length > 0
                        ? whatChanged.changed.map((c) => "- " + (c.old_reason_code || "") + " → " + (c.new_reason_code || "")).join("\n")
                        : "—"}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Caveats */}
            {caveats.length > 0 && (
              <div className="mt-4 p-3 bg-slate-900 rounded-lg">
                <p className="font-medium text-slate-300 text-sm">Caveats</p>
                <div className="grid grid-cols-2 gap-2">
                  {caveats.map((c, i) => (
                    <div key={i} className="bg-slate-700 rounded px-2 py-1 text-caption">
                      {c.reason_code}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Excluded list */}
            {excluded.length > 0 && (
              <div className="mt-4 p-3 bg-slate-900 rounded-lg">
                <p className="font-medium text-slate-300 text-sm">Excluded</p>
                <div className="grid grid-cols-2 gap-2">
                  {excluded.map((e, i) => (
                    <div key={i} className="bg-slate-700 rounded px-2 py-1 text-caption">
                      {e.reason_code}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => setShowProof(true)}
                className="flex-1 rounded-md bg-slate-800 px-4 py-2 text-xs font-medium text-teal-400 hover:bg-slate-700 transition-colors"
                aria-label="Show proof path"
              >
                Show proof path
              </button>
              <button
                onClick={() => setHandoffId(handoffId || undefined)}
                className="flex-1 rounded-md bg-slate-800 px-4 py-2 text-xs font-medium text-violet-400 hover:bg-slate-700 transition-colors"
                aria-label="Open handoff"
              >
                Open handoff
              </button>
            </div>
          </div>
        )}

        {/* Show proof path modal/section */}
        {showProof && answer && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur z-50 flex items-center justify-center p-6">
            <div className="bg-slate-900 rounded-lg p-6 max-w-md mx-8">
              <h3 className="text-xl font-bold text-text mb-3">Proof Path</h3>
              <p className="text-slate-400 mb-4">Source → Claim → Decision → Answer</p>
              <div className="flex gap-3 mb-4">
                <span className="w-3 h-3 rounded-full bg-teal-500 tooltip" title="Source"></span>
                <span className="w-3 h-3 rounded-full bg-amber-500 tooltip" title="Claim"></span>
                <span className="w-3 h-3 rounded-full bg-violet-500 tooltip" title="Decision"></span>
                <span className="w-3 h-3 rounded-full bg-rose-500 tooltip" title="Answer"></span>
              </div>
              <button
                onClick={() => setShowProof(false)}
                className="rounded-md bg-teal-600 px-4 py-2 text-white hover:bg-teal-500 transition-colors"
                aria-label="Close proof path"
              >
                Close
              </button>
            </div>
          </div>
        )}

        {/* Handoff capsule */}
        {handoffId && (
          <HandoffCapsule />
        )}
      </div>
    </div>
  )
}