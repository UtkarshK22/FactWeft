import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { useAppStore } from "../store/useStore"
import { postAsk, postDemoRun } from "../lib/api"

interface AskViewProps {
  llmMode: "fixture" | "live"
}

export function AskView({ llmMode }: AskViewProps) {
  const { selectedMemoryId, selectedHandoffId, asOfMs, filters } = useAppStore((s) => s.panel)
  const [question, setQuestion] = useState("")
  const [answer, setAnswer] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const res = await fetch("/api/health")
      return await res.json()
    },
    enabled: false,
  })

  const { mutate: askMutation } = useMutation({
    mutationFn: async (q: string) => {
      const body: any = { question: q, llm_mode: llmMode }
      if (asOfMs) body.as_of_ms = asOfMs
      if (filters) body.filters = filters
      if (selectedMemoryId) body.selected_memory_id = selectedMemoryId
      if (selectedHandoffId) body.selected_handoff_id = selectedHandoffId
      
      const res = await postAsk(body)
      return res
    },
    onSuccess: (data) => {
      setAnswer(data.answer ?? null)
      showToast("Answer received", "success")
    },
    onError: (err) => {
      showToast(err.message || "Ask failed", "error")
    },
  })

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return
    setIsSubmitting(true)
    askMutation(question)
    setIsSubmitting(false)
    setQuestion("")
  }

  const showToast = (msg: string, type: "success" | "error") => {
    // Use the toast from the API lib or create a simple one
    const div = document.createElement("div")
    const typeStyles: Record<string, string> = {
      success: "bg-green-600 text-white",
      error: "bg-rose-600 text-white",
    }
    div.className = `fixed bottom-4 right-4 p-4 rounded-md max-w-xs opacity-0 transition-opacity duration-300 ${typeStyles[type]}`
    div.textContent = msg
    document.body.appendChild(div)
    setTimeout(() => {
      div.style.opacity = "0"
      setTimeout(() => div.remove(), 300)
    }, 2000)
  }

  // Demo step mappings - these call the real API
  const demoSteps = [
    { key: "seed", label: "Seed", description: "Seed the workspace with initial memories" },
    { key: "reset", label: "Reset", description: "Reset the workspace state" },
    { key: "session1", label: "Run Session 1", description: "Run first demo session" },
    { key: "session2", label: "Run Session 2", description: "Run second demo session" },
    { key: "add_rumour", label: "Add Rumour", description: "Add a rumour memory" },
    { key: "inject_test", label: "Inject Test", description: "Inject test memory" },
    { key: "ask_canonical", label: "Ask canonical", description: "Ask the canonical question" },
  ]

  const handleDemoStep = async (stepKey: string) => {
    const step = demoSteps.find(s => s.key === stepKey)
    if (!step) return
    
    setIsSubmitting(true)
    try {
      const res = await postDemoRun(stepKey)
      setAnswer(`${step.label}: ${JSON.stringify(res?.report || res, null, 2)}`)
      showToast(`${step.label} completed`, "success")
    } catch (err: any) {
      showToast(err.message || `${step.label} failed`, "error")
    }
    setIsSubmitting(false)
  }

  return (
    <section className="prose max-w-none space-y-6">
      {/* Health indicator */}
      {health && health.falkordb === "down" && (
        <div className="p-4 rounded-md bg-rose-600/20 border rose-500/50 border-text mb-4">
          <svg className="h-4 w-4 mr-2 opacity-50" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM9.354 5.646a.5.5 0 0 1 .708 0l1.414 1.414a.5.5 0 0 0 .708-.708l-1.414-1.414a.5.5 0 0 0-.708 0l-1.414 1.414a.5.5 0 0 1-.708 0Z"/>
          </svg>
          <span>Graph is down - memory recall unavailable</span>
        </div>
      )}

      {/* Question form */}
      <div className="p-6 rounded-md bg-bg border border-border">
        <form onSubmit={handleAsk} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text mb-2">
              Question for the agents
            </label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              disabled={isSubmitting}
              className={`
                w-full rounded-md bg-surface border border-border px-3 py-2 
                text-text placeholder-muted focus:outline-none focus:border-accent 
                transition-colors
              `}
              placeholder="What should we do about the release freeze?"
            />
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={isSubmitting || !question.trim()}
              className={`
                inline-flex items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-bg 
                hover:bg-teal-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed
              `}
            >
              {isSubmitting ? "Thinking..." : "Ask Agents"}
            </button>

            {/* Demo buttons */}
            {demoSteps.map((step) => (
              <button
                key={step.key}
                type="button"
                onClick={() => handleDemoStep(step.key)}
                className={`
                  inline-flex items-center rounded-md bg-surface px-3 py-2 text-sm text-muted hover:text-accent hover:bg-bg transition-colors
                `}
                disabled={isSubmitting || health?.falkordb === "down"}
              >
                {step.label}
              </button>
            ))}
          </div>
        </form>
      </div>

      {/* Answer display */}
      {answer && (
        <div className="p-6 rounded-md bg-bg border border-border">
          <h3 className="text-lg font-semibold text-text mb-3">Answer</h3>
          <p className="text-text">{answer}</p>
          {/* Citations */}
          {answer && answer.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border">
              <h4 className="text-sm font-medium text-muted mb-2">Citations</h4>
              <ul className="space-y-1 text-sm text-muted">
                {[answer]
                  .slice(0, 5)
                  .map((citation, i) => (
                    <li key={i} className="flex items-start">
                      <svg className="h-3 w-3 mt-0.5 opacity-60" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 6.252a5.75 5.75 0 1 0 0-11.5 5.75 5.75 0 0 0 0 11.5Zm.177 5.393-3.886 1.895 1.188-4.448.688-3.133 4.448 1.118-4.449 3.317 1.895 3.886-1.118 4.448-3.317 1.188 4.449-.688ZM12 2.252a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z"/>
                      </svg>
                      <span>{citation}</span>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
