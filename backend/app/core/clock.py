"""Epoch-millisecond clock.

Every timestamp stored in FalkorDB is an integer epoch millisecond value.
Formatting happens exclusively in the UI.
"""

from __future__ import annotations

import time


def utc_now_ms() -> int:
    return int(time.time() * 1000)


def epoch_ms(value: str) -> int:
    """Parse an ISO-8601 UTC instant (``Z`` suffix allowed) into epoch ms."""
    from datetime import UTC, datetime

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1000)
