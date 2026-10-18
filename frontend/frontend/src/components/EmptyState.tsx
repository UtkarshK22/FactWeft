import type { ReactNode } from "react"

interface EmptyStateProps {
  icon?: (props: { className?: string }) => ReactNode
  title?: string
  description?: string
  actionLabel?: string
  onAction?: () => void
  suggestedAction?: { label: string; onClick: () => void }
}

export function EmptyState({
  icon: Icon,
  title = "Nothing here yet",
  description = "Start by seeding the workspace with some memories or running a demo session.",
  actionLabel = "Get Started",
  onAction,
  suggestedAction,
}: EmptyStateProps) {
  return (
    <div className="col-span-full min-h-[300px] flex flex-col items-center justify-center gap-4 py-12">
      {Icon && <Icon className="h-12 w-12 text-muted-ops ml-2" />}
      <h3 className="text-lg font-medium text-text">{title}</h3>
      <p className="text-muted text-sm leading-relaxed">{description}</p>
      <div className="flex gap-3">
        {onAction && (
          <button
            onClick={onAction}
            className={`
              inline-flex items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-bg
              hover:bg-teal-400 transition-colors
            `}
          >
            {actionLabel}
          </button>
        )}
        {suggestedAction && (
          <button
            onClick={suggestedAction.onClick}
            className={`
              inline-flex items-center rounded-md bg-surface px-4 py-2 text-sm text-muted 
              hover:text-accent hover:bg-bg transition-colors
            `}
          >
            {suggestedAction.label}
          </button>
        )}
      </div>
    </div>
  )
}
