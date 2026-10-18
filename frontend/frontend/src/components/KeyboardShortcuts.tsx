import { useEffect, type ReactNode } from "react"

interface KeyboardShortcutsProps {
  children: ReactNode
  shortcuts?: Record<string, string>
}

export function KeyboardShortcuts({
  children,
  shortcuts = {
    "g c": "Constellation view",
    "g r": "River view",
    "g d": "Disputes view",
    "g h": "Handoffs view",
    "g a": "Ask view",
    "?": "Show help",
    "Esc": "Close drawers",
  },
}: KeyboardShortcutsProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (!target) return
      // Don't trigger if typing in an input/textarea
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return
      }

      const key = e.key.toLowerCase()
      
      // Handle specific shortcuts
      if (key === "escape") {
        // Close any open modals/drawers
        const openDrawers = document.querySelectorAll("[role=\"dialog\"][open]")
        openDrawers.forEach((drawer) => {
          ;(drawer as HTMLDialogElement).close()
        })
        return
      }

      // Handle shortcuts
      if (shortcuts[key]) {
        e.preventDefault()
        // You could integrate with state management here
        console.log(`Shortcut activated: ${shortcuts[key]}`)
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [shortcuts])

  return (
    <div className="hidden">
      {children}
    </div>
  )
}
