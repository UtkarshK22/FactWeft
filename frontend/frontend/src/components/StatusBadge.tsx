import { ReactNode } from "react"

interface StatusBadgeProps {
  status: "active" | "contested" | "superseded" | "candidate"
  showGlyph?: boolean
}

export function StatusBadge({ status, showGlyph = true }: StatusBadgeProps) {
  const statusClasses = {
    active: "bg-green-600/20 text-green-400 border-green-500/50",
    contested: "bg-amber-600/20 text-amber-400 border-amber-500/50",
    superseded: "bg-slate-600/20 text-slate-400 border-slate-500/50",
    candidate: "bg-violet-600/20 text-violet-400 border-violet-500/50",
  }

  const glyphMap: Record<string, string> = {
    active: "✓",
    contested: "!",
    superseded: "≀",
    candidate: "◉",
  }

  const borderMap: Record<string, string> = {
    active: "solid",
    contested: "double",
    superseded: "dashed",
    candidate: "dotted",
  }

  const cls = statusClasses[status] || statusClasses.active
  const glyph = showGlyph ? glyphMap[status] || "" : ""
  const borderStyle = borderMap[status] || "solid"

  return (
    <span
      className={`
        inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}
        border-${borderStyle}-2 border-y-1.5
      `}
    >
      {glyph}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}
