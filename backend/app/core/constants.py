"""Constants shared by the demo seed, bootstrap and health checks."""

from __future__ import annotations

GRAPH_NAME_PREFIX = "ws_"

# Primary demo workspace (Atlas release readiness).
DEMO_WORKSPACE_ID = "demo_atlas_release_lab"
# Second workspace with deliberately similar concept ids, used for isolation tests.
SECOND_WORKSPACE_ID = "demo_orbit_ops"

DEMO_WORKSPACE_IDS: tuple[str, ...] = (DEMO_WORKSPACE_ID, SECOND_WORKSPACE_ID)

DEMO_WORKSPACE_DISPLAY_NAMES: dict[str, str] = {
    DEMO_WORKSPACE_ID: "Atlas Release Lab",
    SECOND_WORKSPACE_ID: "Orbit Ops",
}
