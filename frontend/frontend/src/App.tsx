import { useState, useEffect, useCallback } from "react"
import { useAppStore } from "./store/useStore"
import { getHealth } from "./lib/api"
import type { AgentInfo, LayoutView } from "./types/api"

// Component imports (will create these next)
import { LeftRail } from "./components/LeftRail"
import { TopBar } from "./components/TopBar"
import { MainCanvas } from "./components/MainCanvas"
import { InspectorDrawer } from "./components/InspectorDrawer"
import { QueryTraceDrawer } from "./components/QueryTraceDrawer"
import { DisputeDesk } from "./components/dispute/DisputeDesk"
import { HandoffCapsule } from "./components/handoff/HandoffCapsule"
import { AskPanel } from "./components/ask/AskPanel"


export function App() {
  const {
    panel,
    setPanel,
    view,
    setView,
    llmMode,
    setLlmMode,
    agent,
    setAgent,
    addToast,
    clearToasts,
  } = useAppStore()

  // Health check polling
  const [isHealthDown, setIsHealthDown] = useState(false)

  useEffect(() => {
    // Initial health check
    checkHealth()

    // Set up interval for health polling (every 3 seconds)
    const interval = setInterval(checkHealth, 3000)

    // Cleanup on unmount
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [])

  const checkHealth = async () => {
    try {
      const health = await getHealth()
      setIsHealthDown(health.falkordb === "down")
    } catch (err) {
      setIsHealthDown(true)
    }
  }

  // Handle agent switcher change
  const handleAgentChange = async (agentInfo: AgentInfo) => {
    setAgent(agentInfo)
    addToast(
      "Agent switched",
      `Acting as ${agentInfo.agent_id} (${agentInfo.role})`,
      "OK"
    )
  }

  // Tab click handler
  const handleTabClick = useCallback((newView: string) => {
    setView(newView as LayoutView)
    clearToasts()
  }, [clearToasts, setView])

  // Escape key handler
  useEffect(() => {
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        // Close any open toasts
        clearToasts()
      }
    }
    document.addEventListener("keydown", handleKeydown)
    return () => document.removeEventListener("keydown", handleKeydown)
  }, [clearToasts])

  // Toast removal on mount
  useEffect(() => {
    clearToasts()
  }, [])

  return (
    <div className="min-h-screen bg-bg text-text flex flex-col">
      {/* Top Bar */}
      <TopBar
        isHealthDown={isHealthDown}
        onAgentChange={handleAgentChange}
        llmMode={llmMode}
        setLlmMode={setLlmMode}
      />

      <div className="flex flex-1 min-w-0">
        {/* Left Rail */}
        <LeftRail
          onTabClick={handleTabClick}
          selectedView={view}
          agent={agent}
        />

        {/* Main Canvas - dynamic view rendering */}
        <MainCanvas
          view={view}
          onTabClick={handleTabClick}
          agent={agent}
          llmMode={llmMode}
        />
      </div>

      {/* View-specific content overlay */}
      {view === "disputes" && (
        <div className="absolute inset-0 flex items-center justify-center bg-bg/80 backdrop-blur z-10">
          <DisputeDesk />
        </div>
      )}
      {view === "handoffs" && (
        <div className="absolute inset-0 flex items-center justify-center bg-bg/80 backdrop-blur z-10">
          <HandoffCapsule />
        </div>
      )}
      {view === "ask" && (
        <div className="absolute inset-0 flex items-center justify-center bg-bg/80 backdrop-blur z-10">
          <AskPanel />
        </div>
      )}

      {/* Right Inspector Drawer */}
      <InspectorDrawer
        panel={panel}
        setPanel={setPanel}
        agent={agent}
        llmMode={llmMode}
      />

      {/* Bottom Query Trace Drawer */}
      <QueryTraceDrawer
        panel={panel}
        setPanel={setPanel}
        agent={agent}
      />
    </div>
  )
}
