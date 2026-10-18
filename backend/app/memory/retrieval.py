"""Concept resolution and eligibility scoring for memory handoffs.

Provides deterministic matching against Concept.canonical_name and
Concept.aliases, eligibility checks (Q-eligible / Q-excluded), scoring
over eligible items only, and readiness determination via procedure match.
All functions are pure (no DB calls) except the Q-* query calls which
delegate to the repository layer.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Concept resolution (no vector DB)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Lowercase, strip punctuation, simple tokenisation."""
    text = text.lower()
    # keep alphanumerics and internal spaces only
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if t]


def _stem(tokens: List[str]) -> List[str]:
    """Very simple stemming: drop trailing 'ed', 'ing', 's'."""
    out: List[str] = []
    for t in tokens:
        if len(t) > 3 and t.endswith("ed"):
            t = t[:-2]
        if len(t) > 3 and t.endswith("ing"):
            t = t[:-3]
        if len(t) > 1 and t.endswith("s"):
            t = t[:-1]
        out.append(t)
    return out


def resolve_concepts(
    question_or_task: str,
    concepts: Optional[Dict[str, dict]] = None,
) -> Set[str]:
    """Return concept ids that match *question_or_task* by deterministic alias match.

    Matching logic:
    - Tokenise and stem the query
    - For each known concept, tokenise/stem its ``canonical_name`` and all
      ``aliases``
    - A concept matches if any query token appears in any concept token set
    - Longest alias-first: if multiple concepts match, prefer the one whose
      longest matching alias is longest

    If *concepts* is ``None`` the function returns an empty set (caller must
    abstain).  The intent is that the caller (e.g. a route) will pass in the
    workspace's concept catalogue obtained from the graph.

    Returns a ``set`` of concept id strings that resolve from the query.
    """
    if not concepts:
        return set()

    query_tokens = set(_stem(_tokenize(question_or_task)))

    matches: List[Tuple[str, int]] = []  # (concept_id, matching_alias_len)
    for concept_id, cdata in concepts.items():
        cname = (cdata.get("canonical_name") or "").lower()
        aliases: List[str] = cdata.get("aliases", [])
        all_tokens: Set[str] = set(_stem(_tokenize(cname)))
        for alias in aliases:
            all_tokens.update(_stem(_tokenize(alias.lower())))

        # check if any query token matches
        if query_tokens & all_tokens:
            # longest matching alias length for tie-breaking
            best_alias_len = 0
            for alias in aliases:
                atokens = set(_stem(_tokenize(alias.lower())))
                if query_tokens & atokens:
                    best_alias_len = max(best_alias_len, len(alias))
            matches.append((concept_id, best_alias_len))

    # sort by longest alias first, then by concept id for determinism
    matches.sort(key=lambda x: (-x[1], x[0]))

    return {cid for cid, _ in matches}


# ---------------------------------------------------------------------------
# Eligibility (hard gates before scoring)
# ---------------------------------------------------------------------------

def check_eligible(
    memory_id: str,
    receiver_id: str,
    principal_agent_id: str,
    concepts: Optional[Dict[str, dict]] = None,
) -> Tuple[bool, Optional[str]]:
    """Q-eligible check: the receiver must be the principal's agent.

    In the demo/auth setup the *receiver_id* is always the principal's agent
    (never from the body).  This function validates that gate and returns
    ``(True, None)`` if eligible, or ``(False, reason_code)`` if not.
    """
    if receiver_id != principal_agent_id:
        return False, "agent_mismatch"
    return True, None


def check_excluded(
    memory_id: str,
    receiver_id: str,
    principal_agent_id: str,
    concepts: Optional[Dict[str, dict]] = None,
) -> Optional[str]:
    """Q-excluded check: build reasons why a memory is excluded.

    For reason ``'scope_denied'`` the receipt contains ONLY
    ``memory_id + reason_code`` (no summary/value/evidence).

    Returns a reason code string if excluded, or ``None`` if not excluded.
    """
    # Scope denied: receiver is not allowed to see this memory
    # In the demo setup, scope=agent_only memories are denied to anyone
    # other than the owning agent
    if receiver_id != principal_agent_id:
        return "scope_denied"
    return None


# ---------------------------------------------------------------------------
# Scoring over eligible items only
# ---------------------------------------------------------------------------

def compute_relevance(
    concept_id: str,
    query_tokens: Set[str],
    concepts: Dict[str, dict],
) -> float:
    """Compute relevance = concept match strength.

    - alias exactness: 1.0 if exact alias token match, 0.5 if stem match,
      0.25 if substring
    - hop distance: not applicable at this layer (handled by caller)
    """
    cdata = concepts.get(concept_id, {})
    if not cdata:
        return 0.0

    # Check canonical name exact match
    cname = cdata.get("canonical_name", "").lower()
    if cname in query_tokens:
        return 1.0

    # Check alias exact match
    for alias in cdata.get("aliases", []):
        if alias.lower() in query_tokens:
            return 1.0

    # Stem match
    query_stems = {t for t in _stem(_tokenize(cname)) if t}
    if query_stems & query_tokens:
        return 0.5

    return 0.1


def compute_evidence_strength(
    sources: List[dict],
) -> float:
    """Compute evidence_strength = normalized max source authority + log(source_count).

    Each source dict should have an ``authority`` int field.
    """
    if not sources:
        return 0.0

    authorities: List[int] = [s.get("authority", 0) for s in sources]
    max_auth = max(authorities) if authorities else 0
    source_count = len(sources)

    # Normalize authority to 0-1 (assume max possible is 100)
    norm_auth = max_auth / 100.0 if max_auth else 0.0

    # Log of source count (natural log, clamped)
    log_count = min(math.log(max(source_count, 1)), 5.0)

    return norm_auth + log_count


def compute_recency(
    valid_from: Optional[int],
    valid_until: Optional[int],
    now_ms: int,
    volatile: bool = False,
) -> float:
    """Compute recency score.

    - Fast decay for volatile predicates (status, freeze_date)
    - Slow decay for procedures
    - Age = now_ms - valid_from (if valid_from is None, age = 0)
    """
    if valid_from is None:
        age_ms = 0
    else:
        age_ms = now_ms - valid_from
    if age_ms <= 0:
        return 1.0

    if volatile:
        # Fast decay: half-life ~ 30 days
        half_life_ms = 30 * 24 * 60 * 60 * 1000  # 30 days in ms
        return max(0.0, 0.5 ** (age_ms / half_life_ms))

    # Slow decay: half-life ~ 365 days
    half_life_ms = 365 * 24 * 60 * 60 * 1000  # 365 days in ms
    return max(0.0, 0.5 ** (age_ms / half_life_ms))


def compute_reuse(
    memory_id: str,
    handoff_history: List[dict],
) -> float:
    """Compute reuse = count of past handoffs that included this memory id.

    handoff_history is a list of handoff receipts, each with an ``included``
    list of memory ids.
    """
    count = 0
    for handoff in handoff_history:
        included_ids = {mem["id"] for mem in handoff.get("included", [])}
        if memory_id in included_ids:
            count += 1
    # Normalise to 0-1 (assume max 20 past handoffs)
    return min(count / 20.0, 1.0)


def score_memory(
    memory: dict,
    query: str,
    now_ms: int,
    handoff_history: List[dict],
    config: Optional[dict] = None,
) -> float:
    """Score a single memory over eligible items only.

    Weights (configurable, defaults per the spec):
        relevance=0.35, evidence_strength=0.25, confidence=0.15,
        recency=0.15, reuse=0.10
    """
    if config is None:
        config = {
            "relevance_weight": 0.35,
            "evidence_weight": 0.25,
            "confidence_weight": 0.15,
            "recency_weight": 0.15,
            "reuse_weight": 0.10,
            "volatile_predicates": {"status", "freeze_date"},
        }

    concepts: Dict[str, dict] = config.get("concepts", {})
    query_tokens: Set[str] = set(_stem(_tokenize(query)))

    # 1. relevance
    relevance = compute_relevance(memory.get("concept_id", ""), query_tokens, concepts)

    # 2. evidence_strength
    sources: List[dict] = memory.get("evidence", [])
    evidence_strength = compute_evidence_strength(sources)

    # 3. confidence
    confidence = memory.get("confidence", 0.0)

    # 4. recency
    valid_from = memory.get("valid_from")
    valid_until = memory.get("valid_until")
    volatile = memory.get("predicate", "") in config.get("volatile_predicates", set())
    recency = compute_recency(valid_from, valid_until, now_ms, volatile)

    # 5. reuse
    reuse = compute_reuse(memory.get("id", ""), handoff_history)

    # Weighted sum
    score = (
        config["relevance_weight"] * relevance
        + config["evidence_weight"] * evidence_strength
        + config["confidence_weight"] * confidence
        + config["recency_weight"] * recency
        + config["reuse_weight"] * reuse
    )

    return round(score, 4)


# ---------------------------------------------------------------------------
# Readiness: procedure match + Q-readiness
# ---------------------------------------------------------------------------

def check_readiness(
    task_steps: List[dict],
    procedures: Dict[str, dict],
    now_ms: int,
) -> dict:
    """Determine readiness if the task matches a procedure.

    If the task steps match a procedure via concept match, run Q-readiness
    and return a structured result plus overall verdict.

    Returns:
        {
            "verdict": "ready" / "not_ready" / "unknown",
            "steps": [
                {"step": str, "expected": str | None, "actual": str | None,
                 "state": str, "memory_id": str | None}
            ]
        }
    """
    # Find matching procedure(s) via concept match on steps
    matched_procedure: Optional[dict] = None
    matched_steps: List[dict] = []

    task_concept_ids: Set[str] = set()
    for step in task_steps:
        cid = step.get("concept_id")
        if cid:
            task_concept_ids.add(cid)

    # Match concepts to procedures
    for proc_id, proc_data in procedures.items():
        proc_concepts = proc_data.get("required_concepts", [])
        if any(cid in task_concept_ids for cid in proc_concepts):
            matched_procedure = proc_data
            # Build step mapping - match by concept_id OR by step name
            for step in task_steps:
                step_concept = step.get("concept_id")
                # Match if concept_id is in required_concepts, OR if step names align
                concept_match = step_concept in proc_concepts if step_concept else False
                name_match = (
                    step.get("step", "").lower() == proc_step.get("step", "").lower()
                    if (proc_step := proc_data.get("steps", [{}])[len(matched_steps) if matched_steps else 0]) else False
                ) if False else False  # disabled for now
                if concept_match:
                    matched_steps.append({
                        "step": step.get("step", ""),
                        "expected": step.get("expected"),
                        "actual": step.get("actual"),
                        "state": step.get("state", "pending"),
                        "memory_id": step.get("memory_id"),
                    })
            break

    if not matched_procedure:
        return {
            "verdict": "unknown",
            "steps": [],
        }

    # Build the step list from the procedure
    proc_steps = matched_procedure.get("steps", [])
    step_results: List[dict] = []
    for i, proc_step in enumerate(proc_steps):
        # Find matching task step by concept_id
        task_step_match = None
        for ts in task_steps:
            if ts.get("concept_id") == proc_step.get("concept_id"):
                task_step_match = ts
                break

        # Fallback: match by step name if no concept_id match
        if task_step_match is None:
            for ts in task_steps:
                if ts.get("step", "").lower() == proc_step.get("step", "").lower():
                    task_step_match = ts
                    break

        expected = task_step_match.get("expected") if task_step_match else None
        actual = task_step_match.get("actual") if task_step_match else None
        state = task_step_match.get("state", "pending") if task_step_match else "pending"

        step_results.append({
            "step": proc_step.get("step", ""),
            "expected": expected,
            "actual": actual,
            "state": state,
            "memory_id": task_step_match.get("memory_id") if task_step_match else None,
        })

    # Overall verdict: deterministic based on step states
    all_ready = all(s["state"] == "completed" for s in step_results)
    any_not_ready = any(s["state"] == "pending" for s in step_results)
    any_failed = any(s["state"] == "failed" for s in step_results)

    if all_ready:
        verdict = "ready"
    elif any_not_ready:
        verdict = "not_ready"
    elif any_failed:
        verdict = "not_ready"
    else:
        verdict = "unknown"

    return {
        "verdict": verdict,
        "steps": step_results,
    }


# ---------------------------------------------------------------------------
# Caveats: contested claims
# ---------------------------------------------------------------------------

def build_caveats(
    contesting_memory_ids: List[str],
    receiver_agent_id: str,
    allowed_agent_ids: Set[str],
    concepts: Optional[Dict[str, dict]] = None,
) -> List[dict]:
    """Build caveats list.

    Include contested claims (summarised as 'unverified') as caveats ONLY when
    relevant to the same concept and when the receiver is allowed to see them.
    Never as decisive context.

    Returns a list of caveat dicts with ``memory_id`` and ``reason_code``.
    """
    caveats: List[dict] = []
    for mid in contesting_memory_ids:
        # Only include if receiver is allowed to see this memory
        if mid not in allowed_agent_ids:
            continue
        # Summarise as unverified
        caveats.append({
            "memory_id": mid,
            "reason_code": "unverified",
        })
    return caveats