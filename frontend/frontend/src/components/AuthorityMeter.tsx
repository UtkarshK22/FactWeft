

interface AuthorityMeterProps {
  pips: number
  active?: number
  className?: string
}

export function AuthorityMeter({ pips, active }: AuthorityMeterProps) {
  const activePips = active || 0

  const pipClasses = (active: boolean) => `
    inline-flex items-center rounded-full w-3 h-3 ${active 
      ? "bg-accent ring-2 ring-ring" 
      : "bg-muted/30 ring-none"
    }
  `

  return (
    <div className="flex gap-1.5">
      {[...Array(pips)].map((_, i) => (
        <span
          key={i}
          className={pipClasses(i < activePips)}
          aria-label={i < activePips ? "active authority pip" : "inactive authority pip"}
        />
      ))}
    </div>
  )
}
