"""Graph-name safety.

One FalkorDB graph per workspace, named ``ws_<workspace_id>``. The name is
derived server-side from the authenticated principal's workspace and validated
before it ever reaches the client library. Client input never becomes a graph
name.
"""

from __future__ import annotations

import re

from app.core.constants import GRAPH_NAME_PREFIX
from app.core.errors import InvalidGraphName

GRAPH_NAME_PATTERN = re.compile(r"^[a-z0-9_]{3,40}$")
# Prefix costs 3 characters, so workspace ids must stay within 37.
WORKSPACE_ID_PATTERN = re.compile(r"^[a-z0-9_]{1,37}$")


def validate_graph_name(graph_name: str) -> str:
    if not isinstance(graph_name, str) or not GRAPH_NAME_PATTERN.match(graph_name):
        raise InvalidGraphName(
            "graph name must match ^[a-z0-9_]{3,40}$ (got an invalid identifier)"
        )
    return graph_name


def graph_name_for_workspace(workspace_id: str) -> str:
    if not isinstance(workspace_id, str) or not WORKSPACE_ID_PATTERN.match(workspace_id):
        raise InvalidGraphName(
            "workspace id must match ^[a-z0-9_]{1,37}$ (graph name is derived from it)"
        )
    graph_name = f"{GRAPH_NAME_PREFIX}{workspace_id}"
    return validate_graph_name(graph_name)
