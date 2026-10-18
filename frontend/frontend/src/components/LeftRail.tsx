import { AgentAvatar } from "./AgentAvatar"

interface LeftRailProps {
  onTabClick: (view: string) => void
  selectedView: string
  agent: any | null
}

export function LeftRail({ onTabClick, selectedView, agent }: LeftRailProps) {

  const views = [
    { key: "constellation", label: "Constellation", icon: "⟡", description: "Memory graph" },
    { key: "river", label: "River", icon: "🌊", description: "Timeline view" },
    { key: "disputes", label: "Disputes", icon: "⚖️", description: "Contested memories" },
    { key: "handoffs", label: "Handoffs", icon: "🔄", description: "Handoff history" },
    { key: "ask", label: "Ask", icon: "❓", description: "Ask the agents" },
  ]

  return (
    <aside
      className="w-16 flex flex-col min-h-screen bg-surface border-r border-border select-none"
    >
      <div className="flex-1 flex flex-col items-center gap-2 pt-2">
        {views.map((view) => (
          <button
            key={view.key}
            onClick={() => onTabClick(view.key)}
            className={`
              w-full flex flex-col items-center rounded-md py-2 px-1 gap-1.5 
              text-sm ${selectedView === view.key 
                ? "text-accent font-medium bg-bg/50" 
                : "text-muted hover:text-accent hover:bg-bg transition-colors"}
              focus:outline-none focus:bg-bg/50 focus:rounded-md
            `}
            aria-current={selectedView === view.key ? "page" : undefined}
            title={view.description}
          >
            <span className="opacity-70">{view.icon}</span>
            <span className="hidden sm:block capitalize text-[0.6em]">{view.label}</span>
          </button>
        ))}
      </div>

      {/* Selection summary */}
      <div className="mt-auto p-3 border-t border-border">
        <div className="text-[0.65em] text-muted mb-1">Selected</div>
        {agent && (
          <AgentAvatar agentId={agent.agent_id} role={agent.role} size="sm" />
        )}
      </div>

      {/* Keyboard shortcuts hint */}
      <div className="p-3 text-[0.65em] text-muted border-t border-border">
        <span className="font-medium">Shortcuts:</span>
        <span className="ml-1">g c / g r / g d / g h / g a</span>
        <span className="ml-2">Esc</span>
      </div>
    </aside>
  )
}
