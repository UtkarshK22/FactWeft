import type { ReactNode } from "react"

interface ErrorStateProps {
  error: unknown
  retry?: () => void
  fallback?: ReactNode
}

export function ErrorState({
  error,
  retry,
  fallback,
}: ErrorStateProps) {
  const errorBody = error as { message?: string; detail?: string; code?: string; status?: number }

  return (
    <div className="rounded-md bg-surface p-6 border border-border">
      {fallback || (
        <div className="mb-4">
          <svg className="h-6 w-6 mx-auto text-rose-400 mb-3 opacity-50" viewBox="0 0 20 20" fill="currentColor">
            <path d="M18 6L9 16l-3-3L6 8l3 3L2 12l3.5 3.5L12 7l-2.5 2.5L7 18l3 3v-6.5a.5.5 0 0 1 1 0V18a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.25M6 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"/>
          </svg>
          <h4 className="text-lg font-medium text-text mb-1">Something went wrong</h4>
          <p className="text-muted text-sm">{errorBody.message || "Please try again later."}</p>
        </div>
      )}

      {retry && (
        <button
          onClick={retry}
          className={`
            inline-flex items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-bg
            hover:bg-teal-400 transition-colors mt-3
          `}
        >
          Retry
        </button>
      )}

      {fallback && <div>{fallback}</div>}
    </div>
  )
}
