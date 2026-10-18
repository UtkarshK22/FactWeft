import { ReactNode } from "react"

interface ScopeChipProps {
  label: string
  count?: number
  active?: boolean
  onSelect?: () => void
}

export function ScopeChip({ label, count, active = false, onSelect }: ScopeChipProps) {
  const classes = `
    inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium 
    transition-colors 
    ${active 
      ? "bg-accent text-bg border-accent-500/50" 
      : "bg-surface text-muted hover:text-accent hover:bg-bg border-border"
    }
  `

  return (
    <div
      className={classes}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      className="cursor-pointer"
    >
      {label}
      {count !== undefined && (
        <span className="ml-1 text-[0.6em] bg-bg rounded-full w-2 h-2 text-accent">{count}</span>
      )}
    </div>
  )
}
