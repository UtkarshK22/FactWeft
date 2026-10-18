"""Identity of the authenticated demo principal."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.core.auth import Principal, get_principal
from app.core.config import Settings
from app.models.api import MeResponse

router = APIRouter(tags=["system"])


@router.get("/me", response_model=MeResponse, summary="Current principal and derived graph")
async def me(
    principal: Annotated[Principal, Depends(get_principal)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> MeResponse:
    return MeResponse(
        workspace_id=principal.workspace_id,
        agent_id=principal.agent_id,
        role=principal.role,
        graph_name=principal.graph_name,
        demo_mode=settings.demo_mode,
        llm_mode=settings.llm_mode,
    )
