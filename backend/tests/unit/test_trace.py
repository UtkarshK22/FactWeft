from __future__ import annotations

from app.core.config import Settings
from app.graph.connection import GraphClient, TraceBuffer, TraceEntry, redact_params


def _entry(index: int) -> TraceEntry:
    return TraceEntry(
        id=f"tr_{index}",
        request_id="req_test",
        query_name=f"q{index}",
        cypher="RETURN 1",
        params={},
        duration_ms=1.0,
        rows=0,
        write=False,
        ts=index,
    )


def test_buffer_is_bounded_and_newest_first() -> None:
    buffer = TraceBuffer(3)
    for index in range(10):
        buffer.add(_entry(index))
    assert len(buffer) == 3
    assert [entry.ts for entry in buffer.snapshot(10)] == [9, 8, 7]
    assert [entry.ts for entry in buffer.snapshot(2)] == [9, 8]
    buffer.clear()
    assert len(buffer) == 0


def test_redaction_masks_secrets_and_truncates_long_values() -> None:
    redacted = redact_params(
        {
            "token": "tok_secret",
            "nested": {"api_key": "sk-123", "safe": "value"},
            "items": [{"password": "hunter2"}],
            "long": "x" * 400,
            "count": 3,
        }
    )
    assert redacted["token"] == "***"
    assert redacted["nested"]["api_key"] == "***"
    assert redacted["nested"]["safe"] == "value"
    assert redacted["items"][0]["password"] == "***"
    assert redacted["long"].endswith("...(truncated)")
    assert len(redacted["long"]) == 240 + len("...(truncated)")
    assert redacted["count"] == 3


def test_client_exposes_empty_trace_buffer_before_use() -> None:
    client = GraphClient(Settings(), buffer_size=5)
    assert client.trace_capacity == 5
    assert client.trace_count == 0
    assert client.recent_traces() == []
