"""API response models (Pydantic v2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.models.domain import Role
from app.models.graph import MemoryRecord, NeighborhoodProjection, SourceEvidence

# HTTP schemas reuse the repository models so there is one definition.
MemoryDetail = MemoryRecord
__all__ = [
    "HealthResponse",
    "MeResponse",
    "MemoryDetail",
    "NeighborhoodProjection",
    "SourceEvidence",
    "TraceEntryResponse",
    "TraceResponse",
]


class HealthResponse(BaseModel):
    api: Literal["ok"] = "ok"
    falkordb: Literal["ok", "down"]
    graph_seeded: bool
    llm_mode: Literal["fixture", "live"]


class MeResponse(BaseModel):
    workspace_id: str
    agent_id: str
    role: Role
    graph_name: str
    demo_mode: bool
    llm_mode: Literal["fixture", "live"]




class TraceEntryResponse(BaseModel):
    id: str
    request_id: str
    query_name: str
    cypher: str
    params: dict[str, Any]
    duration_ms: float
    rows: int
    write: bool
    ts: int
    error: str | None = None


class TraceResponse(BaseModel):
    capacity: int
    count: int
    entries: list[TraceEntryResponse]
