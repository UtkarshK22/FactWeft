import { useEffect, useRef } from "react"

interface ToastProps {
  message: string
  type?: "success" | "error" | "info"
  duration?: number
}

export function Toast({ message, type = "info", duration = 5000 }: ToastProps) {
  const timeoutRef = useRef<number>()
  const toastRef = useRef<HTMLDivElement>()

  useEffect(() => {
    // Create toast element
    const toast = document.createElement("div")
    toastRef.current = toast
    
    const typeStyles: Record<string, string> = {
      success: "bg-green-600 text-white",
      error: "bg-rose-600 text-white",
      info: "bg-teal-600 text-white",
    }

    toast.className = `
      fixed bottom-4 right-4 p-4 rounded-md max-w-xs opacity-0 
      transition-all duration-300 z-50 ${typeStyles[type]}
      shadow-lg
    `
    toast.textContent = message
    document.body.appendChild(toast)
    
    // Trigger entrance
    setTimeout(() => {
      toast.style.opacity = "1"
    }, 100)
    
    // Auto-remove
    timeoutRef.current = window.setTimeout(() => {
      toast.style.opacity = "0"
      setTimeout(() => toast.remove(), 300)
    }, duration)
    
    // Cleanup on unmount
    return () => {
      if (toast.parentNode) toast.parentNode.removeChild(toast)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [message, type, duration])

  // No render needed - it's all done in useEffect
  return null
}
