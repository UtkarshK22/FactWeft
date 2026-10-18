import { useState } from "react"
import { useAppStore } from "../store/useStore"
import { useQuery } from "@tanstack/react-query"
import { getHealth, getMe, setAgent, loadPanelState } from "../lib/api"
import { StatusBadge } from "./StatusBadge"
import { ScopeChip } from "./ScopeChip"
import { AuthorityMeter } from "./AuthorityMeter"
import { AgentAvatar } from "./AgentAvatar"
import { KeyboardShortcuts } from "./KeyboardShortcuts"

interface TopBarProps {
  llmMode: "fixture" | "live"
  setLlmMode: (mode: "fixture" | "live") => void
}

export function TopBar({ llmMode, setLlmMode }: TopBarProps) {
  const { agent, setAgent } = useAppStore()
  const { data: health, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    enabled: false,
  })

  // Agent switcher options
  const agents = [
    { id: "agent_scout", role: "scout", token: "tok_atlas_scout_7c1f9a" },
    { id: "agent_verifier", role: "verifier", token: "tok_atlas_verifier_a3f2b1" },
    { id: "agent_coordinator", role: "coordinator", token: "tok_atlas_coordinator_9e6c02" },
    { id: "agent_owner", role: "owner", token: "tok_atlas_owner_d4e5f3" },
  ]

  const handleAgentSelect = (agentInfo: typeof agents[0]) => {
    setAgent(agentInfo)
    setAgent(agentInfo.token)
  }

  // Health indicator
  const healthStatus = health?.falkordb === "down" ? "down" : health?.falkordb === "ok" ? "ok" : "unknown"

  return (
    <header className="border-b border-border bg-bg/80 backdrop-blur-md sticky top-0 z-20 flex items-center justify-between px-6 py-3">
      <div className="flex items-center gap-4">
        {/* Workspace name */}
        <h1 className="text-lg font-semibold text-text">
          FactWelt Atlas Lab
        </h1>

        {/* LLM mode badge */}
        <div className="flex items-center gap-2 rounded-md px-3 py-1 text-xs">
          <span className={`px-2 py-0.5 rounded ${llmMode === "live" ? "bg-teal-600 text-white" : "bg-violet-600 text-white"}`}>
            {llmMode === "live" ? "Live" : "Fixture"}
          </span>
        </div>
      </div>

      {/* Top bar actions */}
      <div className="flex items-center gap-4">
        {/* Agent switcher */}
        <div className="relative">
          <button
            onClick={(e) => e.stopPropagation()}
            className={`
              flex items-center gap-2 rounded-md bg-surface px-3 py-1.5 text-sm 
              text-muted hover:text-accent hover:bg-bg transition-colors
              focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2
            `}
            aria-haspopup="menu"
            aria-label="Switch acting agent"
          >
            {agent?.agent_id || "Acting as scout"}
            <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M9.293 3.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L10.586 7H7a1 1 0 01-1-1v-4a1 1 0 011-1h3.586z"/>
            </svg>
          </button>

          {/* Agent menu */}
          <ul role="menu" className="absolute right-0 mt-2 w-48 rounded-md bg-bg border border-border p-2 shadow-lg z-30">
            {agents.map((a) => (
              <li key={a.id}>
                <button
                  onClick={() => handleAgentSelect(a)}
                  className={`
                    flex items-center gap-2 rounded-md px-3 py-1.5 text-sm 
                    ${agent?.agent_id === a.id 
                      ? "bg-accent text-bg" 
                      : "text-muted hover:text-accent hover:bg-bg transition-colors"}
                  `}
                >
                  <AgentAvatar agentId={a.agentId} role={a.role} size="sm" />
                  {a.agent_id}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Health indicator */}
        <div className="flex items-center gap-2 rounded-md px-3 py-1.5 text-xs">
          <StatusBadge status={healthStatus} showGlyph={false} />
          <span className="text-muted">{healthStatus === "ok" ? "Graph OK" : healthStatus === "down" ? "Graph DOWN" : "Unknown"}</span>
        </div>

        {/* LLM mode badge */}
        <div className="flex items-center gap-2 rounded-md px-2 py-1 text-xs border border-border">
          <span className={`px-2 py-0.5 rounded ${llmMode === "live" ? "bg-teal-600 text-white" : "bg-violet-600 text-white"}`}>
            {llmMode === "live" ? "Live" : "Fixture"}
          </span>
        </div>

        {/* Demo menu button */}
        <button
          onClick={(e) => e.stopPropagation()}
          className={`
            flex items-center gap-2 rounded-md bg-surface px-3 py-1.5 text-sm text-muted 
            hover:text-accent hover:bg-bg transition-colors
          `}
          aria-haspopup="menu"
          aria-label="Demo menu"
        >
          <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M5.25 5.75a2.75 2.75 0 1 1 5.5 0v5a2.75 2.75 0 1 1-5.5 0V5.75zM5 9.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"/>
          </svg>
          Demo
        </button>

        {/* Help button */}
        <button className="hidden sm:inline-flex items-center gap-2 rounded-md bg-surface px-3 py-1.5 text-sm text-muted hover:text-accent hover:bg-bg transition-colors" aria-label="Help">
          <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M7.293 7.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L8.586 13H5a1 1 0 01-1-1v-4a1 1 0 011-1h3.586z"/>
          </svg>
          ?
        </button>
      </div>
    </header>
  )
}
