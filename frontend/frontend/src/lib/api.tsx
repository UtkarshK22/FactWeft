import type {
  HealthResponse,
  MeResponse,
  AskResponse,
  AskRequest,
  DemoRunResponse,
  AgentInfo,
  PanelState,
  Toast,
  LayoutView,
  Citation,
  Readiness,
  Step,
  WhatChanged,
  Caveat,
  Excluded,
} from "../types/api"

const BASE_URL = "/api"

// Create bearer token interceptor
let bearerToken: string | null = null

export function setBearerToken(token: string | null) {
  bearerToken = token
}

export function getBearerToken(): string | null {
  return bearerToken
}

// Setup token from localStorage on init
if (typeof window !== "undefined") {
  const stored = localStorage.getItem("factweft_token")
  if (stored) {
    setBearerToken(stored)
  }
}

async function request(
  endpoint: string,
  options: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(options.headers)

  // Inject bearer token
  if (bearerToken) {
    headers.set("Authorization", `Bearer ${bearerToken}`)
  }

  // Default content type for JSON body
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json")
  }

  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: "same-origin",
  })

  // Handle 401 - clear stale token
  if (res.status === 401) {
    setBearerToken(null)
    if (typeof window !== "undefined") {
      localStorage.removeItem("factweft_token")
    }
  }

  return res
}

// Health endpoint
export async function getHealth(): Promise<HealthResponse> {
  const res = await request("/health")
  if (!res.ok) throw new Error("Health check failed")
  return res.json()
}

// Me endpoint
export async function getMe(): Promise<MeResponse> {
  const res = await request("/me")
  if (!res.ok) throw new Error("Authentication required")
  return res.json()
}

// Ask endpoint
export async function postAsk(
  body: AskRequest,
): Promise<AskResponse> {
  const res = await request("/ask", {
    method: "POST",
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(
      err.message || `Ask failed with status ${res.status}`,
    )
  }
  return res.json()
}

// Demo run endpoint
export async function postDemoRun(
  step: string,
): Promise<DemoRunResponse> {
  const res = await request(`/demo/run/${step}`)
  if (!res.ok) {
    const err = await res.json()
    throw new Error(
      err.message || `Demo run failed with status ${res.status}`,
    )
  }
  return res.json()
}

// Agent switcher - sets the bearer token
export async function setAgent(token: string) {
  setBearerToken(token)
  if (typeof window !== "undefined") {
    localStorage.setItem("factweft_token", token)
  }
}

// Panel state helpers
export function loadPanelState(): PanelState {
  if (typeof window === "undefined") {
    return {
      selectedMemoryId: null,
      selectedHandoffId: null,
      asOfMs: null,
      filters: {
        kind: null,
        scope: null,
        agent_id: null,
        status: null,
        predicate: null,
        value: null,
      },
    }
  }
  const stored = localStorage.getItem("factweft_panel_state")
  if (stored) {
    return JSON.parse(stored)
  }
  return {
    selectedMemoryId: null,
    selectedHandoffId: null,
    asOfMs: null,
    filters: {
      kind: null,
      scope: null,
      agent_id: null,
      status: null,
      predicate: null,
      value: null,
    },
  }
}

export function savePanelState(state: PanelState) {
  if (typeof window === "undefined") return
  localStorage.setItem("factweft_panel_state", JSON.stringify(state))
}

// Toast management
export type ToastId = string

export function createToast(
  title: string,
  description: string,
  action?: string,
  timeout = 5000,
): ToastId {
  const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`
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
        <p class="font-medium text-sm line-clamp-2">{title}</p>
        <p class="text-xs text-slate-400 line-clamp-1">{description}</p>
      </div>
      {action && `\n        <button class="ml-2 text-xs font-semibold text-accent underline underline-offset-2 hover:opacity-90">\n          ${action}\n        </button>\n      `}
    </div>
  `
  document.body.appendChild(toast)

  // Auto-remove after timeout
  setTimeout(() => {
    toast.remove()
  }, timeout)

  return id
}

// Query keys for TanStack Query
export const queryKeys = {
  health: ["health"],
  me: ["me"],
  memories: (vars: { scope?: string }) => ["memories", vars],
  handoffs: (vars: { scope?: string }) => ["handoffs", vars],
  timeline: (vars: { asOfMs?: number }) => ["timeline", vars],
  ask: (question: string) => ["ask", question],
  demoRun: (step: string) => ["demoRun", step],
}

// Empty and error state components will be created separately
