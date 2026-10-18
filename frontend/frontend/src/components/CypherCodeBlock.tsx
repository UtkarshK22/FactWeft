import { ReactNode, useState } from "react"

interface CypherCodeBlockProps {
  cypher: string
  showCopyButton?: boolean
  onCopy?: () => void
}

export function CypherCodeBlock({
  cypher,
  showCopyButton = true,
  onCopy,
}: CypherCodeBlockProps) {
  const [isCopied, setIsCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(cypher)
      setIsCopied(true)
      if (onCopy) onCopy()
      // Auto-reset after 2 seconds
      setTimeout(() => setIsCopied(false), 2000)
    } catch (err) {
      // Fallback for IE
      const textarea = document.createElement("textarea")
      textarea.value = cypher
      document.body.appendChild(textarea)
      textarea.select()
      try {
        document.execCommand("copy")
      } catch (e) {
        console.error("Copy fallback failed", e)
      }
      document.body.removeChild(textarea)
      setIsCopied(true)
      setTimeout(() => setIsCopied(false), 2000)
    }
  }

  return (
    <div className="rounded-md bg-surface p-4 border border-border">
      <div className="overflow-x-auto">
        <pre 
          className="text-[0.75em] text-mono leading-relaxed whitespace-pre-wrap"
        >
          {cypher}
        </pre>
      </div>

      {showCopyButton && (
        <button
          onClick={handleCopy}
          className={`
            mt-3 inline-flex items-center rounded-md bg-bg px-3 py-1.5 text-xs font-medium 
            text-muted hover:text-accent hover:bg-bg transition-colors 
            ${isCopied ? "bg-accent/20 text-accent" : ""}
          `}
          aria-label={isCopied ? "Copied!" : "Copy Cypher"}
        >
          {isCopied ? (
            <>
              <svg className="h-3.5 w-3.5 mr-1.5 opacity-80" viewBox="0 0 20 20" fill="currentColor">
                <path d="M8.517 5.35a.75.75 0 0 1 1.063-.683l3.197 1.552a.75.75 0 0 1-.108 1.253l-3.197-1.552a.75.75 0 0 1-.682-.683ZM6.25 13.75a.75.75 0 0 1-1.062-.17l-1.651 2.317.057.818a.75.75 0 0 1-.58.288l-2.708.768-1.651-2.317a.75.75 0 0 1-.17-1.062l2.088-1.162 1.846.023a.75.75 0 0 1 .598.305l1.366 2.685-.838 3.1a.75.75 0 0 1-.55.156l-2.01-1.836-1.651 2.317a.75.75 0 0 1-1.062-.17l-.187-.808 2.708-.768a.75.75 0 0 1 .58-.288l1.651-2.317-.057-.818a.75.75 0 0 1 .58-.288Z"/>
              </svg>
              Copied!
            </>
          ) : (
            <>
              <svg className="h-3.5 w-3.5 mr-1.5 opacity-80" viewBox="0 0 20 20" fill="currentColor">
                <path d="M8.517 5.35a.75.75 0 0 1 1.063-.683l3.197 1.552a.75.75 0 0 1-.108 1.253l-3.197-1.552a.75.75 0 0 1-.682-.683ZM6.25 13.75a.75.75 0 0 1-1.062-.17l-1.651 2.317.057.818a.75.75 0 0 1-.58.288l-2.708.768-1.651-2.317a.75.75 0 0 1-.17-1.062l2.088-1.162 1.846.023a.75.75 0 0 1 .598.305l1.366 2.685-.838 3.1a.75.75 0 0 1-.55.156l-2.01-1.836-1.651 2.317a.75.75 0 0 1-1.062-.17l-.187-.808 2.708-.768a.75.75 0 0 1 .58-.288l1.651-2.317-.057-.818a.75.75 0 0 1 .58-.288Z"/>
              </svg>
              Copy
            </>
          )}
        </button>
      )}
    </div>
  )
}
