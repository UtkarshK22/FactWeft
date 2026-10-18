"""Demo control endpoints.

Both routes act on the **principal's own workspace** (never a body parameter),
require the ``owner`` role and are only available while ``DEMO_MODE`` is on.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings, get_graph_client
from app.core.auth import Principal, require_roles
from app.core.config import Settings
from app.core.errors import DemoDisabled
from app.graph.connection import GraphClient
from app.memory.seed import reset_workspace, seed_workspace
from app.models.domain import Role

router = APIRouter(tags=["demo"])

OwnerOnly = Annotated[Principal, Depends(require_roles(Role.OWNER))]


async def require_demo_mode(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> Settings:
    if not settings.demo_mode:
        raise DemoDisabled("Demo endpoints are disabled (DEMO_MODE=false)")
    return settings


DemoMode = Annotated[Settings, Depends(require_demo_mode)]


@router.post(
    "/demo/seed",
    summary="Seed the static base of the caller's workspace (idempotent)",
)
async def demo_seed(
    principal: OwnerOnly,
    client: Annotated[GraphClient, Depends(get_graph_client)],
    _settings: DemoMode,
) -> dict[str, Any]:
    report = await seed_workspace(principal.workspace_id, client=client)
    return report.as_dict()


@router.post(
    "/demo/reset",
    summary="Drop the caller's workspace graph and recreate an empty schema",
)
async def demo_reset(
    principal: OwnerOnly,
    client: Annotated[GraphClient, Depends(get_graph_client)],
    _settings: DemoMode,
) -> dict[str, Any]:
    report = await reset_workspace(principal.workspace_id, client=client)
    return report.as_dict()
