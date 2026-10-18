from __future__ import annotations

import json

import pytest
from app.core.auth import TokenFileError, TokenRegistry, get_principal, require_roles
from app.core.config import Settings
from app.core.errors import AuthRequired, InvalidGraphName, RoleForbidden
from app.models.domain import Role


@pytest.fixture
def registry(settings: Settings) -> TokenRegistry:
    return TokenRegistry.load(settings.tokens_path)


def test_demo_tokens_resolve_to_principals(registry: TokenRegistry) -> None:
    scout = registry.resolve("tok_atlas_scout_7c1f9a")
    assert scout is not None
    assert scout.workspace_id == "demo_atlas_release_lab"
    assert scout.agent_id == "agent_scout"
    assert scout.role is Role.SCOUT
    assert scout.graph_name == "ws_demo_atlas_release_lab"
    assert registry.resolve("not-a-token") is None
    assert set(registry.workspace_ids) == {"demo_atlas_release_lab", "demo_orbit_ops"}
    assert len(registry.for_workspace("demo_orbit_ops")) == 5


def test_duplicate_tokens_are_rejected(tmp_path) -> None:
    path = tmp_path / "tokens.json"
    path.write_text(
        json.dumps(
            {
                "principals": [
                    {"token": "same", "workspace_id": "ws_a", "agent_id": "a", "role": "scout"},
                    {"token": "same", "workspace_id": "ws_a", "agent_id": "b", "role": "scout"},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(TokenFileError):
        TokenRegistry.load(path)


def test_invalid_role_is_rejected(tmp_path) -> None:
    path = tmp_path / "tokens.json"
    path.write_text(
        json.dumps(
            {
                "principals": [
                    {"token": "t", "workspace_id": "ws_a", "agent_id": "a", "role": "wizard"}
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(TokenFileError):
        TokenRegistry.load(path)


def test_unsafe_workspace_id_is_rejected(tmp_path) -> None:
    path = tmp_path / "tokens.json"
    path.write_text(
        json.dumps(
            {
                "principals": [
                    {"token": "t", "workspace_id": "WS A", "agent_id": "a", "role": "scout"}
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(InvalidGraphName):
        TokenRegistry.load(path)


async def test_missing_or_malformed_bearer_is_rejected(registry: TokenRegistry) -> None:
    with pytest.raises(AuthRequired):
        await get_principal(None, registry)
    with pytest.raises(AuthRequired):
        await get_principal("Basic abc", registry)
    with pytest.raises(AuthRequired):
        await get_principal("Bearer unknown", registry)
    principal = await get_principal("Bearer tok_atlas_scout_7c1f9a", registry)
    assert principal.agent_id == "agent_scout"


async def test_require_roles_enforces_membership(registry: TokenRegistry) -> None:
    dependency = require_roles(Role.VERIFIER, Role.OWNER)
    scout = registry.resolve("tok_atlas_scout_7c1f9a")
    owner = registry.resolve("tok_atlas_owner_4f0b13")
    assert scout is not None and owner is not None
    with pytest.raises(RoleForbidden):
        await dependency(scout)
    assert await dependency(owner) is owner
