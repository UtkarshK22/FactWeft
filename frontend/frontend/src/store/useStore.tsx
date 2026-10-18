import create from "zustand"
import { persist } from "zustand/middleware/persist"

// Types
import type {
  PanelState,
  FilterState,
  LayoutView,
  Toast,
  ToastId,
  Citation,
  Readiness,
  Step,
  WhatChanged,
  AgentInfo,
} from "../types/api"

// Toast management
const createToastElement = (id: ToastId) => {
  const toast = document.createElement("div")
  toast.id = id
  toast.className = "fixed top-4 right-4 max-w-xs w-full bg-slate-900/90 border border-slate-700 rounded-xl p-4 shadow-lg animate-in slide-in-from-top-0 z-50"
  toast.setAttribute("role", "alert")
  toast.setAttribute("aria-live", "polite")
  toast.innerHTML = `
    <div class="flex items-start">
      <div class="flex-shrink-0 flex w-6 h-6 flex-col items-center justify-center rounded-sm bg-accent text-bg">
        <svg class="h-5 w-5 text-bg" viewBox="0 0 20 20" fill="currentColor">
          <path d="M16.723 5.172a.75.75 0 0 0-1.06-1.06L12.5 11.233l-3.978-3.978a.75.75 0 0 0-1.061.95l3.536 3.536H5.75a.75.75 0 0 1-.75-.75v-8a.75.75 0 0 1 .75-.75h8a.75.75 0 0 1 .75.75v1.563l3.036-2.108a.75.75 0 1 0-.217-1.35L8.5 6.126l-1.837-3.871a.75.75 0 0 0-1.057-.087H5.25a.75.75 0 0 1-.75-.75v-8a.75.75 0 0 1 .75-.75h8a.75.75 0 0 1 .75.75v4.875L12.5 13.653l5.05-3.313a.75.75 0 1 0-.217-1.35zM5.75 13.25a1.25 1.25 0 1 1 0-2.5 1.25 1.25 0 0 1 0 2.5Zm8.5 0a1.25 1.25 0 1 1 0-2.5 1.25 1.25 0 0 1 0 2.5Z"/>
        </svg>
      </div>
      <div class="flex-1 flex flex-col pt-1">
        <p class="font-medium text-sm line-clamp-2"></p>
        <p class="text-xs text-slate-400 line-clamp-1"></p>
      </div>
    </div>
  `
  ;(document.body as HTMLElement).appendChild(toast)
  return toast
}

export function removeToastElement(id: ToastId) {
  const elem = document.getElementById(id)
  if (elem) elem.remove()
}

export interface AppState {
  // Panel / selection state
  panel: PanelState
  setPanel: (partial: Partial<PanelState>) => void

  // Current view
  view: LayoutView
  setView: (view: LayoutView) => void

  // LLM mode
  llmMode: "fixture" | "live"
  setLlmMode: (mode: "fixture" | "live") => void

  // Agent info
  agent: AgentInfo | null
  setAgent: (agent: AgentInfo | null) => void

  // Toast system
  toasts: Record<ToastId, Toast>
  addToast: (title: string, description: string, action?: string, timeout?: number) => ToastId
  removeToast: (id: ToastId) => void
  clearToasts: () => void

  // Query client refs (for TanStack Query)
  queryClient: any
  setQueryClient: (client: any) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // Initial state
      panel: loadPanelState(),
      setPanel: (partial) => {
        const next = { ...get().panel, ...partial }
        savePanelState(next)
        set({ panel: next })
      },

      view: "constellation",
      setView: (v) => set({ view: v }),

      llmMode: "fixture",
      setLlmMode: (mode) => set({ llmMode: mode }),

      agent: null,
      setAgent: (a) => {
        set({ agent: a })
        if (a) {
          setBearerToken(a.token)
          localStorage.setItem("factweft_token", a.token)
        } else {
          setBearerToken(null)
          localStorage.removeItem("factweft_token")
        }
      },

      toasts: {},
      addToast: (title, description, action, timeout = 5000) => {
        const id = createToastElement(`toast-${Date.now()}-${Math.random().toString(36).slice(2)}`)
        const toast: Toast = { id, title, description, action }
        set((s) => ({
          toasts: { ...s.toasts, [id]: toast },
        }))
        return id
      },
      removeToast: (id) => {
        removeToastElement(id)
        set((s) => ({
          toasts: Object.fromEntries(
            Object.entries(s.toasts).filter(([key]) => key !== id),
          ),
        }))
      },
      clearToasts: () => {
        Object.values(get().toasts).forEach((t) => removeToastElement(t.id))
        set({ toasts: {} })
      },

      // Query client reference
      queryClient: null,
      setQueryClient: (client) => set({ queryClient: client }),
    }),

    {
      name: "factweft-storage",
      partialize: (state) => ({
        panel: {
          selectedMemoryId: state.panel.selectedMemoryId,
          selectedHandoffId: state.panel.selectedHandoffId,
          asOfMs: state.panel.asOfMs,
        },
      }),
    }
  ),
)