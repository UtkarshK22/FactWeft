"""Typed results for the Cypher catalogue.

Every repository function returns one of these models; raw FalkorDB rows never
leave ``app/graph/repo.py``. Nullable fields mirror the graph schema (for
example ``valid_until`` is absent until a memory is superseded).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SourceEvidence(BaseModel):
    id: str
    title: str | None = None
    authority: int | None = None


class MemoryRecord(BaseModel):
    id: str
    kind: str | None = None
    subject_key: str | None = None
    predicate: str | None = None
    object_value: str | None = None
    cardinality: str | None = None
    summary: str | None = None
    status: str | None = None
    scope: str | None = None
    confidence: float | None = None
    created_at: int | None = None
    valid_from: int | None = None
    valid_until: int | None = None
    superseded_at: int | None = None
    revision: int | None = None
    proposed_by: str | None = None
    concept_name: str | None = None
    evidence: list[SourceEvidence] = Field(default_factory=list)


class ProposedMemory(BaseModel):
    memory_id: str
    status: str


class EpisodeLink(BaseModel):
    memory_id: str
    episode_id: str


class ValidUntilUpdate(BaseModel):
    memory_id: str
    valid_until: int | None = None


class ShareLink(BaseModel):
    memory_id: str
    agent_id: str


class ConflictCandidate(BaseModel):
    """One active memory that contradicts a candidate (Q3)."""

    existing_id: str
    existing_value: str | None = None
    existing_valid_from: int | None = None
    existing_revision: int | None = None
    cand_valid_from: int | None = None
    existing_authority: int | None = None
    existing_published_at: int | None = None
    cand_authority: int | None = None
    cand_published_at: int | None = None


class Corroboration(BaseModel):
    existing_id: str
    existing_revision: int | None = None


class SupersedeResult(BaseModel):
    new_id: str
    old_id: str


class MemoryStatusResult(BaseModel):
    memory_id: str
    status: str


class CoexistResult(BaseModel):
    candidate_id: str
    existing_id: str


class EligibleMemory(BaseModel):
    id: str
    kind: str | None = None
    predicate: str | None = None
    value: str | None = None
    summary: str | None = None
    confidence: float | None = None
    valid_from: int | None = None
    concept_id: str | None = None
    evidence: list[SourceEvidence] = Field(default_factory=list)


class IneligibleMemory(BaseModel):
    id: str
    reason_code: str
    summary: str | None = None


class ReadinessStep(BaseModel):
    step_order: int
    step: str
    expected: str | None = None
    memory_id: str | None = None
    actual: str | None = None
    state: str


class HandoffCreated(BaseModel):
    handoff_id: str


class HandoffLinkCounts(BaseModel):
    count: int


class WhySource(BaseModel):
    id: str
    title: str | None = None
    source_type: str | None = None
    authority: int | None = None
    published_at: int | None = None
    excerpt: str | None = None


class WhySupersedes(BaseModel):
    older_ids: list[str] = Field(default_factory=list)
    newer_ids: list[str] = Field(default_factory=list)


class WhyDecision(BaseModel):
    id: str
    decision_type: str | None = None
    outcome: str | None = None
    reason_code: str | None = None
    reviewer_type: str | None = None
    decided_at: int | None = None


class WhyHandoff(BaseModel):
    handoff_id: str
    relation: str
    reason_code: str | None = None
    created_at: int | None = None


class TimelineEvent(BaseModel):
    memory_id: str | None = None
    at_ms: int | None = None
    event_type: str
    status: str | None = None
    summary: str | None = None
    predicate: str | None = None
    object_value: str | None = None
    episode_id: str | None = None
    agent_id: str | None = None


class DisputeRecord(BaseModel):
    candidate_id: str
    predicate: str | None = None
    candidate_value: str | None = None
    candidate_summary: str | None = None
    candidate_valid_from: int | None = None
    candidate_revision: int | None = None
    candidate_authority: int | None = None
    existing_id: str
    existing_value: str | None = None
    existing_summary: str | None = None
    existing_valid_from: int | None = None
    existing_revision: int | None = None
    existing_authority: int | None = None
    decision_ids: list[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    labels: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class NeighborhoodCounts(BaseModel):
    shown_nodes: int
    total_nodes: int
    shown_edges: int
    showing: str


class NeighborhoodProjection(BaseModel):
    root_id: str
    hops: int
    as_of_ms: int | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    counts: NeighborhoodCounts
    truncated: bool
