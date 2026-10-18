import type { ReactNode } from "react"

// Health endpoint
export type HealthResponse = {
  api: "ok"
  falkordb: "ok" | "down"
  graph_seeded: boolean
  llm_mode: "fixture" | "live"
}

// Me endpoint
export type MeResponse = {
  workspace_id: string
  agent_id: string
  role: string
  graph_name: string
  demo_mode: boolean
  llm_mode: "fixture" | "live"
}

// Memory detail
export type MemoryDetail = {
  id: string
  kind: string | null
  subject_key: string | null
  predicate: string | null
  object_value: string | null
  cardinality: string | null
  summary: string | null
  status: string | null
  scope: string | null
  confidence: float | null
  created_at: int | null
  valid_from: int | null
  valid_until: int | null
  superseded_at: int | null
  revision: int | null
  proposed_by: string | null
  concept_name: string | null
  evidence: Array<{ id: string; title: string; authority: number | null }>
}

// Auth error
export type AuthError = {
  error: "auth_required"
}

// 404 error
export type NotFoundError = {
  error: "not_found"
  request_id: string
}

// 422 unprocessable claim
export type UnprocessableError = {
  error: "unprocessable_claim"
  reason: string
  detail?: string
}

// 503 graph unavailable
export type GraphUnavailableError = {
  error: "graph_unavailable"
  message: string
}

// Ask request
export type AskRequest = {
  question: string
  llm_mode?: "fixture" | "live"
}

// Ask response
export type AskResponse = {
  answer: string
  citations: Citation[]
  caveats: Caveat[]
  excluded: Excluded[]
  handoff_id: string
  readiness: Readiness
  what_changed: WhatChanged
  llm_mode: string
  grounding: "extracted" | "template"
  trace_ids: string[]
}

// Citation
export type Citation = {
  id: string
  predicate: string
  value: string
}

// Caveat
export type Caveat = {
  memory_id: string
  reason_code: string
}

// Excluded
export type Excluded = {
  id: string
  reason_code: string
}

// Readiness
export type Readiness = {
  verdict: "ready" | "not_ready" | "unknown"
  steps: Step[]
}

export type Step = {
  step: string
  expected: string | null
  actual: string | null
  state: "completed" | "pending" | "failed"
  memory_id: string | null
}

// What changed
export type WhatChanged = {
  added: Added[]
  removed: Removed[]
  changed: Changed[]
}

export type Added = {
  id: string
  summary: string | null
  evidence: string | null
}

export type Removed = {
  id: string
  reason_code: string
}

export type Changed = {
  id: string
  old_reason_code: string | null
  new_reason_code: string | null
}

// Demo run response
export type DemoRunResponse = {
  step: string
  report: any
}

// Agent switcher
export type AgentInfo = {
  agent_id: string
  role: string
  token: string
}

// Panel state
export type PanelState = {
  selectedMemoryId: string | null
  selectedHandoffId: string | null
  asOfMs: number | null
  filters: FilterState
}

export type FilterState = {
  kind: string | null
  scope: string | null
  agent_id: string | null
  status: string | null
  predicate: string | null
  value: string | null
}

// Toast
export type Toast = {
  id: string
  title: string
  description: string
  action?: string
}

// Main layout
export type LayoutView = "constellation" | "river" | "disputes" | "handoffs" | "ask"
