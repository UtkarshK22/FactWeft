from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

SCOUT = {"Authorization": "Bearer tok_atlas_scout_7c1f9a"}
COORDINATOR = {"Authorization": "Bearer tok_atlas_coordinator_9e6c02"}


@pytest.fixture
def api_client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def dead_client(settings: Settings) -> Iterator[TestClient]:
    dead = settings.model_copy(update={"falkordb_port": 6390, "query_timeout_ms": 500})
    with TestClient(create_app(dead)) as client:
        yield client


def test_health_reports_falkordb_ok(api_client: TestClient) -> None:
    response = api_client.get("/api/health")
    body = response.json()
    assert response.status_code == 200
    assert body["api"] == "ok"
    assert body["falkordb"] == "ok"
    assert body["llm_mode"] in {"fixture", "live"}
    assert "X-Request-ID" in response.headers


def test_request_id_header_is_echoed(api_client: TestClient) -> None:
    response = api_client.get("/api/health", headers={"X-Request-ID": "req_test_123"})
    assert response.headers["X-Request-ID"] == "req_test_123"


def test_me_requires_a_bearer_token(api_client: TestClient) -> None:
    response = api_client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["error"] == "auth_required"


def test_me_returns_principal_and_derived_graph(api_client: TestClient) -> None:
    response = api_client.get("/api/me", headers=SCOUT)
    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == "demo_atlas_release_lab"
    assert body["agent_id"] == "agent_scout"
    assert body["role"] == "scout"
    assert body["graph_name"] == "ws_demo_atlas_release_lab"


def test_unknown_memory_is_404_within_the_principal_boundary(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/memories/definitely_missing", headers=SCOUT)
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["request_id"]


def test_trace_requires_coordinator(api_client: TestClient) -> None:
    assert api_client.get("/api/trace", headers=SCOUT).status_code == 403
    response = api_client.get("/api/trace?limit=5", headers=COORDINATOR)
    assert response.status_code == 200
    body = response.json()
    assert body["capacity"] >= 1
    assert isinstance(body["entries"], list)


def test_health_reports_down_when_falkordb_is_unreachable(dead_client: TestClient) -> None:
    response = dead_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["falkordb"] == "down"
    assert body["graph_seeded"] is False


def test_graph_route_returns_503_when_falkordb_is_unreachable(
    dead_client: TestClient,
) -> None:
    response = dead_client.get("/api/memories/anything", headers=SCOUT)
    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "graph_unavailable"
    assert "local copy" in body["message"]
