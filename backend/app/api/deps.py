"""FastAPI dependencies backed by app state (easy to override in tests)."""

from __future__ import annotations

from fastapi import Request

from app.core.config import Settings
from app.graph.connection import GraphClient


def get_app_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise RuntimeError("app settings are not initialised")
    return settings


def get_graph_client(request: Request) -> GraphClient:
    client = getattr(request.app.state, "graph_client", None)
    if not isinstance(client, GraphClient):
        raise RuntimeError("graph client is not initialised")
    return client
