"""Typed access to ``demo_data/*.json``.

The JSON is fictional and validated on load: every extraction fixture must key a
declared source, every claim must reference a declared concept and episode with a
predicate the procedure knows how to check. A typo in the demo data fails loudly
at seed time instead of producing a half-seeded graph.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings

DEMO_DATA_FILES: dict[str, str] = {
    "demo_atlas_release_lab": "atlas_release_lab.json",
    "demo_orbit_ops": "orbit_ops.json",
}


class UnknownDemoWorkspace(ValueError):
    """No demo data file is registered for this workspace id."""


class DemoWorkspaceInfo(BaseModel):
    id: str
    display_name: str
    created_at: int


class DemoAgent(BaseModel):
    id: str
    role: str
    display_name: str


class DemoConcept(BaseModel):
    id: str
    canonical_name: str
    concept_type: str
    aliases: list[str] = Field(default_factory=list)


class DemoSource(BaseModel):
    id: str
    title: str
    source_type: str
    source_ref: str
    published_at: int
    authority: int = Field(ge=1, le=5)
    synthetic_flag: bool = True
    excerpt: str
    content_hash: str

    @field_validator("content_hash")
    @classmethod
    def _hash_shape(cls, value: str) -> str:
        if not value.startswith("sha256:") or len(value) != len("sha256:") + 64:
            raise ValueError("content_hash must be 'sha256:<64 hex chars>'")
        return value


class DemoSession(BaseModel):
    id: str
    task_label: str
    started_at: int
    ended_at: int | None = None


class DemoEpisode(BaseModel):
    id: str
    session_id: str
    event_type: str
    occurred_at: int
    summary: str


class DemoStep(BaseModel):
    order: int
    label: str
    check_predicate: str
    expected_value: str
    concept_id: str


class DemoProcedure(BaseModel):
    id: str
    agent_id: str
    subject_key: str
    predicate: str
    label: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: int
    valid_from: int
    steps: list[DemoStep] = Field(default_factory=list)


class ExtractionClaim(BaseModel):
    """One candidate claim a source yields in fixture (offline) mode."""

    subject_key: str
    predicate: str
    object_value: str
    kind: str = "semantic"
    cardinality: str = "one"
    summary: str
    scope: str = "workspace"
    confidence: float = Field(ge=0.0, le=1.0)
    valid_from: int
    episode_id: str | None = None


class ExtractionFixture(BaseModel):
    claims: list[ExtractionClaim] = Field(default_factory=list)
    note: str | None = None


class ScratchClaim(ExtractionClaim):
    """A private note an agent records without a source of its own.

    The scenario runner attaches it to ``source_id`` with the declaring agent so
    the demo can show scope denial (agent_only is invisible to other agents).
    """

    source_id: str
    agent_id: str = "agent_scout"


class DemoWorkspace(BaseModel):
    workspace: DemoWorkspaceInfo
    agents: list[DemoAgent]
    concepts: list[DemoConcept]
    sources: list[DemoSource]
    sessions: list[DemoSession]
    episodes: list[DemoEpisode]
    procedures: list[DemoProcedure]
    extractions: dict[str, ExtractionFixture] = Field(default_factory=dict)
    scratch_claims: list[ScratchClaim] = Field(default_factory=list)

    def validate_references(self) -> DemoWorkspace:
        concept_ids = {concept.id for concept in self.concepts}
        source_ids = {source.id for source in self.sources}
        session_ids = {session.id for session in self.sessions}
        episode_ids = {episode.id for episode in self.episodes}
        agent_ids = {agent.id for agent in self.agents}

        for episode in self.episodes:
            if episode.session_id not in session_ids:
                raise ValueError(f"episode {episode.id} references unknown session {episode.session_id}")
        for procedure in self.procedures:
            if procedure.subject_key not in concept_ids:
                raise ValueError(f"procedure {procedure.id} references unknown concept")
            if procedure.agent_id not in agent_ids:
                raise ValueError(f"procedure {procedure.id} references unknown agent")
            for step in procedure.steps:
                if step.concept_id not in concept_ids:
                    raise ValueError(f"step {step.label} references unknown concept")
        for source_id, fixture in self.extractions.items():
            if source_id not in source_ids:
                raise ValueError(f"extraction fixture keys unknown source {source_id}")
            for claim in fixture.claims:
                if claim.subject_key not in concept_ids:
                    raise ValueError(f"claim on {claim.subject_key} references unknown concept")
                if claim.episode_id is not None and claim.episode_id not in episode_ids:
                    raise ValueError(f"claim references unknown episode {claim.episode_id}")
        for claim in self.scratch_claims:
            if claim.subject_key not in concept_ids:
                raise ValueError(f"scratch claim on {claim.subject_key} references unknown concept")
            if claim.source_id not in source_ids:
                raise ValueError(f"scratch claim references unknown source {claim.source_id}")
            if claim.agent_id not in agent_ids:
                raise ValueError(f"scratch claim references unknown agent {claim.agent_id}")
            if claim.episode_id is not None and claim.episode_id not in episode_ids:
                raise ValueError(f"scratch claim references unknown episode {claim.episode_id}")
        return self


def demo_data_dir() -> Path:
    """``demo_data/`` lives next to the token file (mounted into the container)."""
    return get_settings().tokens_path.parent


@lru_cache(maxsize=4)
def load_demo_workspace(workspace_id: str) -> DemoWorkspace:
    filename = DEMO_DATA_FILES.get(workspace_id)
    if filename is None:
        raise UnknownDemoWorkspace(f"no demo data file registered for {workspace_id!r}")
    path = demo_data_dir() / filename
    if not path.is_file():
        raise UnknownDemoWorkspace(f"demo data file missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    data = DemoWorkspace(**payload)
    if data.workspace.id != workspace_id:
        raise ValueError(
            f"{path.name} declares workspace {data.workspace.id!r}, expected {workspace_id!r}"
        )
    return data.validate_references()


def demo_workspace_ids() -> tuple[str, ...]:
    return tuple(DEMO_DATA_FILES)
