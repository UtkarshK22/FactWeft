from __future__ import annotations

import pytest
from app.core.errors import InvalidGraphName
from app.graph.names import graph_name_for_workspace, validate_graph_name


@pytest.mark.parametrize(
    "name",
    ["ws_demo_atlas_release_lab", "ws_a", "abc", "a" * 40, "ws_demo_orbit_ops"],
)
def test_valid_graph_names(name: str) -> None:
    assert validate_graph_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        "ws",
        "WS_demo",
        "ws-demo",
        "ws demo",
        "ws_demo;DROP GRAPH",
        " ws_demo",
        "a" * 41,
        "ws_ünïcode",
    ],
)
def test_invalid_graph_names(name: str) -> None:
    with pytest.raises(InvalidGraphName):
        validate_graph_name(name)


def test_graph_name_is_derived_from_workspace() -> None:
    assert graph_name_for_workspace("demo_atlas_release_lab") == "ws_demo_atlas_release_lab"


@pytest.mark.parametrize("workspace_id", ["Demo", "demo-lab", "", "x" * 38, "demo lab"])
def test_invalid_workspace_ids(workspace_id: str) -> None:
    with pytest.raises(InvalidGraphName):
        graph_name_for_workspace(workspace_id)
