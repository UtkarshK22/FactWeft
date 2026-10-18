"""Canonical domain vocabulary (mirrors the graph model exactly)."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    SCOUT = "scout"
    VERIFIER = "verifier"
    PLANNER = "planner"
    COORDINATOR = "coordinator"
    OWNER = "owner"


class MemoryKind(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
    EXPIRED = "expired"


class MemoryScope(StrEnum):
    AGENT_ONLY = "agent_only"
    HANDOFF = "handoff"
    WORKSPACE = "workspace"


class Cardinality(StrEnum):
    ONE = "one"
    MANY = "many"


class ReviewerType(StrEnum):
    RULE = "rule"
    HUMAN = "human"
    AGENT = "agent"


class ExclusionReason(StrEnum):
    """Stable receipt reason codes; also used for handoff EXCLUDES edges."""

    SUPERSEDED = "superseded_by_newer_supported_claim"
    CONTESTED = "contested"
    UNPROMOTED_CANDIDATE = "unpromoted_candidate"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SCOPE_DENIED = "scope_denied"
    BUDGET_EXCEEDED = "budget_exceeded"


class DecisionReason(StrEnum):
    NEWER_HIGHER_AUTHORITY = "newer_higher_authority"
    LOWER_AUTHORITY = "lower_authority"
    NEEDS_REVIEW = "needs_review"
    CORROBORATED = "corroborated"


# Which capabilities each role holds. Used by ``require_roles`` call sites.
ROLE_CAPABILITIES: dict[Role, frozenset[str]] = {
    Role.SCOUT: frozenset({"propose"}),
    Role.VERIFIER: frozenset({"propose", "review"}),
    Role.PLANNER: frozenset({"ask", "handoff"}),
    Role.COORDINATOR: frozenset({"propose", "review", "ask", "handoff", "trace", "demo"}),
    Role.OWNER: frozenset(
        {"propose", "review", "ask", "handoff", "trace", "demo", "dispute_resolve"}
    ),
}
