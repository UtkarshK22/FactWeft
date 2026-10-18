import { React } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { App } from "./App"
import { useAppStore } from "./store/useStore"

// Initialize TanStack Query client
const queryClient = new QueryClient()

// Make query client available globally
useAppStore.setQueryClient(queryClient)

// Wait for DOM content to be ready before rendering
document.addEventListener("DOMContentLoaded", () => {
  // Check for saved agent token on startup
  if (typeof window !== "undefined") {
    const storedToken = localStorage.getItem("factweft_token")
    if (storedToken) {
      useAppStore.getState().setAgent({ agent_id: "agent_demo", role: "scout", token: storedToken })
    }
  }

  const root = createRoot(document.getElementById("root")!)
  root.render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>
  )
})
