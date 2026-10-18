interface QueryTraceDrawerProps {
  panel: any
  setPanel: any
  agent: any | null
}

export function QueryTraceDrawer({ panel, setPanel }: QueryTraceDrawerProps) {
  const { asOfMs } = panel

  return (
    <div className={`fixed left-0 top-0 bottom-0 w-80 transform transition-transform duration-300 ease-in-out ${
      panel.selectedHandoffId ? "translate-x-0" : "translate-x-full"
    } bg-bg border-r border-border z-40 overflow-y-auto`}>
      <button
        onClick={() => setPanel({ ...panel, selectedHandoffId: null })}
        className="absolute top-3 left-3 p-1 rounded-md bg-surface hover:bg-bg transition-colors"
        aria-label="Close trace drawer"
      >
        <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path d="M9.049 8.6l6.47-6.47a2 2 0 012.82 0L14.925 10h-1.44l-5.333 5.333a2 2 0 01-2.82 0L3.6 10H1.562a2 2 0 01-2-1.736 2.003 2.003 0 00-1.838.386l-1.167 1.565a2.003 2.003 0 00.386 1.837L1.562 16.3a2 2 0 01-2 1.736L1.414 18a2 2 0 01-2 1.736 2.003 2.003 0 00-.386 1.837l1.167 1.565a2.003 2.003 0 00.386 1.837L7.08 20H5.25l5.333-5.333a2 2 0 010 2.82zM9.5 9.25a1.25 1.25 0 110-2.5 1.25 1.25 0 010 2.5z"/>
        </svg>
      </button>

      {/* Drawer header */}
      <div className="p-4 border-b border-border">
        <h2 className="text-lg font-semibold text-text">Query Trace</h2>
        <button onClick={() => setPanel({ ...panel, selectedHandoffId: null })} className="text-muted float-right">Close</button>
      </div>

      {/* Trace content */}
      <div className="p-4 flex-1 h-full">
        {asOfMs && (
          <div className="mb-4 p-3 rounded-md bg-surface border border-border">
            <h3 className="text-sm font-medium text-text mb-1">asOf (ms)</h3>
            <p className="text-muted text-mono">{asOfMs}</p>
          </div>
        )}

        <div>
          <h3 className="text-sm font-medium text-text mb-2">Recent Queries</h3>
          <div className="space-y-1 max-h-80 overflow-y-auto">
            {/* Trace entries would be rendered here */}
            <div className="p-2 rounded-md text-[0.65em] text-muted">
              No queries recorded yet
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border">
        <button
          onClick={() => setPanel({ ...panel, selectedHandoffId: null })}
          className={`
            w-full rounded-md px-4 py-2 text-sm font-medium 
            bg-surface text-muted hover:text-accent hover:bg-bg transition-colors
          `}
        >
          Close
        </button>
      </div>
    </div>
  )
}
