"""Pure conflict-resolution logic — no DB calls.

``resolve(candidate, existing)`` takes the Q3 conflict row (a dict or
``ConflictCandidate``) and returns ``{action, reason_code}`` so the caller
can decide whether to promote, hold, supersede or corroborate without touching
the graph.  This is the unit-testable core of the master spec's deterministic
resolver.
"""

from __future__ import annotations

from typing import Any


class ConflictCandidate(dict[str, Any]):
    """Q3 conflict row — the caller must ensure the fields it needs are present."""

    existing_id: str
    existing_value: str | None = None
    existing_valid_from: int | None = None
    existing_revision: int | None = None
    cand_valid_from: int | None = None
    existing_authority: int | None = None
    existing_published_at: int | None = None
    cand_authority: int | None = None
    cand_published_at: int | None = None


def resolve(candidate: ConflictCandidate, existing: ConflictCandidate) -> dict[str, str]:
    """Determine the action and reason code from a Q3 conflict row.

    Rules (verified against the pinned FalkorDB v4.22.1 behaviour):

    1. **Same value** → corroborate (no conflict, just link SUPPORTED_BY).
    2. **Higher authority wins** — if ``cand_authority > existing_authority``,
       the candidate supersedes.
    3. **Equal authority, newer valid_from wins** — the newer claim wins.
    4. **Lower authority, newer valid_from** → the candidate is *held* (stays
       candidate, a CONTRADICTS edge is added but status stays ``candidate``).
    5. **Older valid_from is held** — if the existing claim was valid From an
       earlier epoch, the candidate is held.
    6. **Cardinality ``many``** — never a conflict, regardless of values.
    7. **Same value, different summary** — treat as corroboration.

    Returns a dict with ``"action"`` and ``"reason_code"`` keys.
    ``action`` is one of: ``"promote"``, ``"hold"``, ``"supersede"``,
    ``"corroborate"``.
    ``reason_code`` is one of: ``None``, ``"duplicate_corroborated"``,
    ``"lower_authority"``, ``"equal_authority_newer"``,
    ``"newer_but_lower_authority"``, ``"older_valid_from"``, ``"many_never_conflict"``.
    """
    # Rule 6: cardinality many never conflicts
    if existing.get("existing_valid_from") is not None and existing.get("_cardinality_many"):
        return {"action": "promote", "reason_code": "many_never_conflict"}

    # Extract compare values
    cand_auth = existing.get("cand_authority", 0) or 0
    exist_auth = existing.get("existing_authority", 0) or 0
    cand_valid = existing.get("cand_valid_from") or 0
    exist_valid = existing.get("existing_valid_from") or 0
    cand_val = (existing.get("cand_value") or "").strip()
    exist_val = (existing.get("existing_value") or "").strip()

    # Rule 1: same value → corroborate
    if cand_val == exist_val and cand_val:
        return {"action": "corroborate", "reason_code": "duplicate_corroborated"}

    # Rule 2: higher authority wins
    if cand_auth > exist_auth:
        return {"action": "supersede", "reason_code": "newer_higher_authority"}

    # Rule 3: equal authority, newer valid_from wins
    if cand_auth == exist_auth and cand_valid > exist_valid:
        return {"action": "promote", "reason_code": "equal_authority_newer"}

    # Rule 4: lower authority, newer valid_from → held
    if cand_auth < exist_auth and cand_valid > exist_valid:
        return {"action": "hold", "reason_code": "newer_but_lower_authority"}

    # Rule 5: older valid_from is held
    if exist_valid > 0 and exist_valid > cand_valid:
        return {"action": "hold", "reason_code": "older_valid_from"}

    # Default fall-through — promote (should not happen with complete data)
    return {"action": "promote", "reason_code": None}


# Convenient helper for callers who already have dict rows from Q3.
def classify_conflict(candidate: dict[str, Any], existing: dict[str, Any]) -> tuple[str, str | None]:
    """Return ``(action, reason_code)`` from plain Q3 return rows.

    The Q3 statement returns rows with these columns (among others):

    ``existing_id``, ``existing_value``, ``existing_valid_from``,
    ``existing_revision``, ``cand_valid_from``, ``existing_authority``,
    ``existing_published_at``, ``cand_authority``, ``cand_published_at``.

    This wrapper pulls those keys safely and delegates to :func:`resolve`.
    """
    c = ConflictCandidate(candidate)
    e = ConflictCandidate(existing)
    result = resolve(c, e)
    return result["action"], result["reason_code"]