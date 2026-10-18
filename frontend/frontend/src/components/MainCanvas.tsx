import { ReactNode } from "react"
import { useAppStore } from "../store/useStore"
import { useQuery } from "@tanstack/react-query"
import { getHealth } from "../lib/api"
import { useNavigate } from "react-router-dom"
import { useAppStore as useStore } from "../store/useStore"

interface MainCanvasProps {
  view: string
  onTabClick: (view: string) => void
  agent: any | null
  llmMode: string
}

export function MainCanvas({ view, onTabClick, agent, llmMode }: MainCanvasProps) {
  const { data: health, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    enabled: false,
  })

  // Tab buttons
  const tabs = [
    { key: "constellation", label: "Constellation", icon: "⟡" },
    { key: "river", label: "River", icon: "🌊" },
    { key: "disputes", label: "Disputes", icon: "⚖️" },
    { key: "handoffs", label: "Handoffs", icon: "🔄" },
    { key: "ask", label: "Ask", icon: "❓" },
  ]

  return (
    <main
      className="flex-1 overflow-y-auto p-6 space-y-6"
    >
      {/* Tab navigation */}
      <div className="border-b border-border pb-4">
        <div className="flex gap-2 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => onTabClick(tab.key)}
              className={view === tab.key
                ? "inline-flex items-center rounded-md bg-bg px-4 py-2 text-sm font-medium text-accent shadow-sm"
                : "inline-flex items-center rounded-md bg-transparent px-4 py-2 text-sm text-muted hover:text-accent hover:bg-bg transition-colors"}
              aria-current={view === tab.key ? "page" : undefined}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content area */}
      <div className="prose max-w-none">
        {isLoading && (
          <div className="min-h-[400px] flex items-center justify-center text-muted">
            <SkeletonLoader size="large" />
          </div>
        )}

        {data && data.falkordb === "down" && (
          <div className="min-h-[400px] flex items-center justify-center text-rose-400">
            <svg className="h-6 w-6 mb-2 opacity-50" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM9.354 5.646a.5.5 0 0 1 .708 0l1.414 1.414a.5.5 0 0 0 .708-.708l-1.414-1.414a.5.5 0 0 0-.708 0l-1.414 1.414a.5.5 0 0 1-.708 0Z"/>
            </svg>
            <span>Graph is down - memory recall unavailable</span>
          </div>
        )}

        {/* View-specific content would go here */}
        {view === "ask" && (
          <AskView llmMode={llmMode} />
        )}

        {view === "handoffs" && (
          <div className="prose">
            <h2 className="text-xl font-semibold text-text mb-4">Handoffs</h2>
            <p className="text-muted">Select a view from the left rail to see handoff data.</p>
          </div>
        )}

        {view === "disputes" && (
          <div className="prose">
            <h2 className="text-xl font-semibold text-text mb-4">Disputes</h2>
            <p className="text-muted">Select a view from the left rail to see dispute data.</p>
          </div>
        )}

        {view === "constellation" && (
          <div className="prose">
            <h2 className="text-xl font-semibold text-text mb-4">Constellation</h2>
            <p className="text-muted">Select a view from the left rail to see constellation data.</p>
          </div>
        )}

        {view === "river" && (
          <div className="prose">
            <h2 className="text-xl font-semibold text-text mb-4">River</h2>
            <p className="text-muted">Select a view from the left rail to see river data.</p>
          </div>
        )}
      </div>
    </main>
  )
}
