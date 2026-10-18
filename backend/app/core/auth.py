"""Demo authentication.

``Authorization: Bearer <token>`` maps to a ``Principal`` loaded from
``demo_data/tokens.json``. The principal is the **only** source of
``workspace_id`` and ``agent_id``; request bodies can never choose a workspace
or a retrieval receiver.

Demo tokens are synthetic and intentionally checked with ``hmac.compare_digest``
(no timing signal, no external identity provider).
"""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, Header

from app.core.config import get_settings
from app.core.errors import AuthRequired, RoleForbidden
from app.graph.names import graph_name_for_workspace
from app.models.domain import Role


class TokenFileError(RuntimeError):
    """The demo token file is missing or malformed (fail fast at startup)."""


@dataclass(frozen=True, slots=True)
class Principal:
    workspace_id: str
    agent_id: str
    role: Role
    token: str = field(repr=False)

    @property
    def graph_name(self) -> str:
        """Graph name derived server-side; never accepted from a request."""
        return graph_name_for_workspace(self.workspace_id)

    def as_dict(self) -> dict[str, str]:
        return {
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "role": self.role.value,
        }


class TokenRegistry:
    def __init__(self, principals: tuple[Principal, ...]) -> None:
        if not principals:
            raise TokenFileError("token registry is empty")
        self._principals = principals

    @classmethod
    def load(cls, path: Path) -> TokenRegistry:
        if not path.is_file():
            raise TokenFileError(f"token file not found: {path}")
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TokenFileError(f"token file is not valid JSON: {path}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("principals"), list):
            raise TokenFileError("token file must contain a 'principals' list")

        principals: list[Principal] = []
        seen_tokens: set[str] = set()
        seen_agents: set[tuple[str, str]] = set()
        for index, raw in enumerate(payload["principals"]):
            where = f"principals[{index}]"
            if not isinstance(raw, dict):
                raise TokenFileError(f"{where} must be an object")
            try:
                token = str(raw["token"]).strip()
                workspace_id = str(raw["workspace_id"]).strip()
                agent_id = str(raw["agent_id"]).strip()
                role = Role(str(raw["role"]).strip())
            except (KeyError, ValueError) as exc:
                raise TokenFileError(f"{where} is missing or has an invalid field: {exc}") from exc
            if not token or not agent_id:
                raise TokenFileError(f"{where} must define a token and an agent_id")
            # Raises InvalidGraphName if a workspace id cannot yield a safe graph name.
            graph_name_for_workspace(workspace_id)
            if token in seen_tokens:
                raise TokenFileError(f"{where} duplicates an existing token")
            if (workspace_id, agent_id) in seen_agents:
                raise TokenFileError(f"{where} duplicates an existing agent in this workspace")
            seen_tokens.add(token)
            seen_agents.add((workspace_id, agent_id))
            principals.append(
                Principal(
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    role=role,
                    token=token,
                )
            )
        return cls(tuple(principals))

    def resolve(self, token: str) -> Principal | None:
        for principal in self._principals:
            if hmac.compare_digest(principal.token, token):
                return principal
        return None

    @property
    def principals(self) -> tuple[Principal, ...]:
        return self._principals

    @property
    def workspace_ids(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for principal in self._principals:
            seen.setdefault(principal.workspace_id, None)
        return tuple(seen)

    def for_workspace(self, workspace_id: str) -> tuple[Principal, ...]:
        return tuple(p for p in self._principals if p.workspace_id == workspace_id)


@lru_cache(maxsize=1)
def get_token_registry() -> TokenRegistry:
    """Load and validate the demo token file once per process."""
    return TokenRegistry.load(get_settings().tokens_path)


def get_registry() -> TokenRegistry:
    """FastAPI dependency indirection so tests can override the registry."""
    return get_token_registry()


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise AuthRequired("Authorization: Bearer <token> is required")
    scheme, _, credentials = authorization.partition(" ")
    token = credentials.strip()
    if scheme.lower() != "bearer" or not token:
        raise AuthRequired("Authorization header must use the Bearer scheme")
    return token


async def get_principal(
    authorization: Annotated[str | None, Header()] = None,
    registry: TokenRegistry = Depends(get_registry),
) -> Principal:
    token = _extract_bearer(authorization)
    principal = registry.resolve(token)
    if principal is None:
        raise AuthRequired("Unknown bearer token")
    return principal


def require_roles(*allowed: Role):
    """Dependency factory: 403 unless the principal holds one of ``allowed`` roles."""
    allowed_set = frozenset(allowed)

    async def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed_set:
            raise RoleForbidden(
                f"role '{principal.role.value}' is not allowed for this action",
                detail={"allowed_roles": sorted(role.value for role in allowed_set)},
            )
        return principal

    return dependency
