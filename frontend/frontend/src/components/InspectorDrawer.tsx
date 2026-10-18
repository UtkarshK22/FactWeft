import { useState } from "react"
import { useAppStore } from "../store/useStore"
import { StatusBadge } from "./StatusBadge"
import { ScopeChip } from "./ScopeChip"

interface InspectorDrawerProps {
  panel: any
  setPanel: any
  agent: any | null
  llmMode: "fixture" | "live"
}

export function InspectorDrawer({ panel, llmMode }: InspectorDrawerProps) {
  const filters = useAppStore((s) => s.panel.filters)
  const [isOpen, setIsOpen] = useState(false)

  const toggle = () => setIsOpen(!isOpen)

  return (
    <div className={`fixed right-0 top-0 bottom-0 w-80 transform transition-transform duration-300 ease-in-out ${
      isOpen ? "translate-x-0" : "translate-x-full"
    } bg-bg border-l border-border z-40 overflow-y-auto`}>
      <button
        onClick={toggle}
        className="absolute top-3 right-3 p-1 rounded-md bg-surface hover:bg-bg transition-colors"
        aria-label="Close inspector"
      >
        <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path d="M9.049 8.6l6.47-6.47a2 2 0 012.82 0L14.925 10h-1.44l-5.333 5.333a2 2 0 01-2.82 0L3.6 10H1.562a2 2 0 01-2-1.736 2.003 2.003 0 00-1.838.386l-1.167 1.565a2.003 2.003 0 00.386 1.837L1.562 16.3a2 2 0 01-2 1.736L1.414 18a2 2 0 01-2 1.736 2.003 2.003 0 00-.386 1.837l1.167 1.565a2.003 2.003 0 00.386 1.837L7.08 20H5.25l5.333-5.333a2 2 0 010 2.82zM9.5 9.25a1.25 1.25 0 110-2.5 1.25 1.25 0 010 2.5z"/>
        </svg>
      </button>

      {/* Drawer header */}
      <div className="p-4 border-b border-border">
        <h2 className="text-lg font-semibold text-text">Inspector</h2>
        <button onClick={toggle} className="text-muted hover:text-accent float-right">
          Close
        </button>
      </div>

      {/* Panel content */}
      <div className="p-4 flex-1">
        {/* Selected memory */}
        {panel.selectedMemoryId && (
          <div className="mb-4 p-3 rounded-md bg-surface border border-border">
            <h3 className="text-sm font-medium text-text mb-1">Selected Memory</h3>
            <p className="text-muted truncate">{panel.selectedMemoryId}</p>
          </div>
        )}

        {/* Selected handoff */}
        {panel.selectedHandoffId && (
          <div className="mb-4 p-3 rounded-md bg-surface border border-border">
            <h3 className="text-sm font-medium text-text mb-1">Selected Handoff</h3>
            <p className="text-muted truncate">{panel.selectedHandoffId}</p>
          </div>
        )}

        {/* asOfMs */}
        {panel.asOfMs && (
          <div className="mb-4 p-3 rounded-md bg-surface border border-border">
            <h3 className="text-sm font-medium text-text mb-1">asOf (ms)</h3>
            <p className="text-muted">{panel.asOfMs}</p>
          </div>
        )}

        {/* Filters */}
        {Object.values(filters ?? {}).some(v => v) && (
          <div className="mb-4 p-3 rounded-md bg-surface border border-border">
            <h3 className="text-sm font-medium text-text mb-1">Filters</h3>
            <div className="grid grid-cols-2 gap-2 text-[0.65em]">
              {filters.kind && (
                <div>
                  <ScopeChip label="kind" count={null} active={filters.kind !== null} />
                  <span className="ml-1">{filters.kind}</span>
                </div>
              )}
              {filters.scope && (
                <div>
                  <ScopeChip label="scope" count={null} active={filters.scope !== null} />
                  <span className="ml-1">{filters.scope}</span>
                </div>
              )}
              {filters.agent_id && (
                <div>
                  <ScopeChip label="agent" count={null} active={filters.agent_id !== null} />
                  <span className="ml-1">{filters.agent_id}</span>
                </div>
              )}
              {filters.status && (
                <div>
                  <StatusBadge status={filters.status as any} showGlyph={false} />
                  <span className="ml-1">{filters.status}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border">
        <button
          onClick={toggle}
          className={`
            w-full rounded-md px-4 py-2 text-sm font-medium 
            ${llmMode === "live" ? "bg-teal-600 text-white" : "bg-violet-600 text-white"}
            hover:bg-teal-400 hover:bg-opacity-90 transition-colors
          `}
        >
          Close
        </button>
      </div>
    </div>
  )
}
