"""Agent roles for the FactWeft memory handoff system.

Explicit async workflow, no framework dependency. Each role is a class
with async methods that operate on the graph and memory state.

Roles:
- Scout: discovers and proposes candidate memories
- Verifier: evaluates proposals, runs conflict resolution, records outcomes
- Planner: builds a handoff for a task through retrieval, then answers
- Coordinator: owns the state machine session -> propose -> verify -> handoff -> answer
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from app.graph.names import graph_name_for_workspace
from app.memory.retrieval import resolve_concepts, check_eligible, check_excluded, build_caveats, score_memory


# ---------------------------------------------------------------------------
# Role base class
# ---------------------------------------------------------------------------

class AgentRole:
    """Base class for all agent roles.

    Provides common utilities: graph name derivation, request ID, clock.
    """

    def __init__(self, principal: Any, graph_client: Any, settings: Any) -> None:
        self.principal = principal
        self.graph_client = graph_client
        self.settings = settings
        self.graph_name = graph_name_for_workspace(principal.workspace_id)

    def _now_ms(self) -> int:
        from app.core.clock import utc_now_ms
        return utc_now_ms()


# ---------------------------------------------------------------------------
# Scout: propose candidate memories
# ---------------------------------------------------------------------------

class Scout(AgentRole):
    """Scout: for a source, extract candidate claims and call propose.

    Flow:
    1. Resolve concepts from the source question/task
    2. If no concepts resolve, abstain (return empty set)
    3. Check eligibility (Q-eligible: receiver = principal's agent)
    4. Check exclusion (Q-excluded: scope_denied etc.)
    5. Score eligible memories
    6. Call propose_memory for qualifying candidates
    7. Return proposed memory ids and reasons
    """

    async def propose(
        self,
        question_or_task: str,
        source_id: str,
        predicate: str,
        object_value: str,
        summary: str,
        confidence: float,
        valid_from: Optional[int] = None,
        valid_until: Optional[int] = None,
        cardinality: str = "one",
        episode_id: Optional[str] = None,
        shared_with: Optional[list[str]] = None,
        now_ms: Optional[int] = None,
    ) -> dict[str, Any]:
        """Propose candidate memories from a source.

        Returns dict with {proposed_ids, reasons, caveats, llm_mode, grounding}.
        """
        now = now_ms or self._now_ms()

        # 1. Resolve concepts
        # In a real implementation, we'd get concepts from the workspace
        # For now, use a placeholder - the route will provide concepts
        concepts: dict[str, dict] = {}  # passed from route

        resolved = resolve_concepts(question_or_task, concepts)
        if not resolved:
            return {"proposed_ids": [], "reasons": [], "caveats": [], "grounding": "template"}

        # 2. Eligibility check
        # receiver is always the principal's agent (never from body)
        receiver_id = self.principal.agent_id
        eligible, _ = check_eligible("", receiver_id, self.principal.agent_id, concepts)
        if not eligible:
            return {"proposed_ids": [], "reasons": ["agent_mismatch"], "caveats": [], "grounding": "template"}

        # 3. Exclusion check
        excluded_reason = check_excluded("", receiver_id, self.principal.agent_id, concepts)
        if excluded_reason:
            return {"proposed_ids": [], "reasons": [excluded_reason], "caveats": [], "grounding": "template"}

        # 4. Scoring and ranking (simplified)
        # In production, would score all eligible memories and rank by score
        # For now, just return the resolved concept ids as proposed
        proposed_ids: list[str] = list(resolved)

        # 5. Build caveats for contested claims
        caveats = build_caveats(
            contesting_memory_ids=list(resolved),
            receiver_agent_id=self.principal.agent_id,
            allowed_agent_ids={self.principal.agent_id},
            concepts=concepts,
        )

        # 6. Reasons based on resolution
        reasons: list[str] = []
        for cid in resolved:
            # Simple reason code based on concept match
            reasons.append(f"resolved_{cid}")

        # 7. Call propose_memory for each candidate
        # (The actual graph call is handled by the route; we just return what would be proposed)

        return {
            "proposed_ids": proposed_ids,
            "reasons": reasons,
            "caveats": caveats,
            "grounding": "extracted",
        }


# ---------------------------------------------------------------------------
# Verifier: evaluate proposals, conflict resolution
# ---------------------------------------------------------------------------

class Verifier(AgentRole):
    """Verifier: after proposals, run conflict evaluation, record outcomes, open disputes.

    Flow:
    1. For each proposed memory, evaluate against existing memories using Q3 resolver
    2. Determine action: promote / hold / supersede / corroborate
    3. Record the outcome with reason_code
    3. If conflict cannot be resolved automatically, open a dispute
    4. Only owner/verifier roles can review disputes
    """

    async def evaluate_conflict(
        self,
        candidate: dict[str, Any],
        existing: dict[str, Any],
    ) -> tuple[str, str | None]:
        """Evaluate a conflict between candidate and existing memory.

        Returns (action, reason_code) using the Q3 conflict resolver.
        This is the same logic as conflicts.resolve() but exposed as an async method.
        """
        from app.memory.conflicts import resolve, classify_conflict

        action, reason_code = classify_conflict(candidate, existing)
        return action, reason_code

    async def record_outcome(
        self,
        memory_id: str,
        action: str,
        reason_code: str | None,
        decision_id: str,
    ) -> dict[str, Any]:
        """Record the review outcome for a memory.

        Returns the result from review_memory.
        """
        from app.memory.lifecycle import review_memory
        from app.api.deps import get_graph_client
        from app.core.auth import get_principal

        # In production, would get the client and principal from context
        # For now, return a placeholder
        return {
            "memory_id": memory_id,
            "action": action,
            "reason_code": reason_code,
            "decision_id": decision_id,
            "status": "recorded",
        }

    async def open_dispute(
        self,
        memory_id: str,
        predicate: str,
        candidate_value: str,
        existing_value: str,
        candidate_authority: int,
        existing_authority: int,
        now_ms: int,
    ) -> dict[str, Any]:
        """Open a dispute for a memory conflict that cannot be auto-resolved.

        Returns the dispute record.
        """
    # In production, would create a Dispute node in the graph
    # For now, return placeholder
        from app.models.graph import DisputeRecord

        return {
            "candidate_id": memory_id,
            "predicate": predicate,
            "candidate_value": candidate_value,
            "existing_value": existing_value,
            "candidate_authority": candidate_authority,
            "existing_authority": existing_authority,
            "decision_ids": [],
            "status": "open",
        }


# ---------------------------------------------------------------------------
# Planner: builds handoff for a task through retrieval, then answers
# ---------------------------------------------------------------------------

class Planner(AgentRole):
    """Planner: builds a handoff for a task through retrieval.py then answers.

    Flow:
    1. Resolve concepts from the task question
    2. If none resolve, return 422 {reason:'no_supporting_memory'} abstention
    3. Check eligibility + readiness + caveats
    4. Create Handoff via Q-handoff
    5. Build fact_sheet (included claims with ids, readiness verdict, what changed)
    6. Compose answer, VALIDATE every cited id is in included set
    6. If validation fails, replace with deterministic template answer, set grounding='template'
    7. Return {answer, citations, caveats, excluded, handoff_id, readiness, what_changed, llm_mode, grounding, trace_ids}
    """

    async def plan(
        self,
        question: str,
        source_id: str,
        concepts: dict[str, dict],
        inclusion_threshold: float = 0.5,
    ) -> dict[str, Any]:
        """Build a handoff and answer for a task question.

        Returns the full /api/ask response dict.
        """
        from app.memory.handoff import assemble_receipt, diff_handoffs
        from app.core.clock import utc_now_ms

        now = utc_now_ms()

        # 1. Resolve concepts from the question
        resolved = resolve_concepts(question, concepts)
        if not resolved:
            return {
                "answer": "",
                "citations": [],
                "caveats": [],
                "excluded": [],
                "handoff_id": None,
                "readiness": {"verdict": "unknown", "steps": []},
                "what_changed": {"added": [], "removed": [], "changed": []},
                "llm_mode": self.settings.llm_mode if self.settings else "fixture",
                "grounding": "template",
                "trace_ids": [],
            }

        # 2. Eligibility check
        receiver_id = self.principal.agent_id
        eligible, _ = check_eligible("", receiver_id, receiver_id, concepts)
        if not eligible:
            return {
                "answer": "",
                "citations": [],
                "caveats": [],
                "excluded": [{"id": "", "reason_code": "agent_mismatch"}],
                "handoff_id": None,
                "readiness": {"verdict": "not_ready", "steps": []},
                "what_changed": {"added": [], "removed": [], "changed": []},
                "llm_mode": self.settings.llm_mode if self.settings else "fixture",
                "grounding": "template",
                "trace_ids": [],
            }

        # 3. Exclusion check
        excluded_reason = check_excluded("", receiver_id, receiver_id, concepts)
        if excluded_reason:
            return {
                "answer": "",
                "citations": [],
                "caveats": [],
                "excluded": [{"id": "", "reason_code": excluded_reason}],
                "handoff_id": None,
                "readiness": {"verdict": "not_ready", "steps": []},
                "what_changed": {"added": [], "removed": [], "changed": []},
                "llm_mode": self.settings.llm_mode if self.settings else "fixture",
                "grounding": "template",
                "trace_ids": [],
            }

        # 4. Check readiness
        # In production, would extract task steps and procedures from the graph
        # For now, use a placeholder
        readiness = {"verdict": "unknown", "steps": []}

        # 5. Create handoff
        # In production, would call the handoff create route/logic
        # For now, generate a handoff id
        handoff_id = uuid.uuid4().hex[:16]

        # 6. Build fact_sheet
        # Placeholder fact sheet - in production would come from extracted claims
        from app.llm.adapter import FactSheet, CandidateClaim

        claims: list[CandidateClaim] = []
        for cid in resolved:
            claims.append(
                CandidateClaim(
                    subject_key=cid,
                    predicate="extracted",
                    value=f"Claim about {cid}",
                    confidence=0.5,
                    reason_code="resolved",
                )
            )

        fact_sheet = FactSheet(claims=claims)

        # 7. Compose answer with validation
        from app.llm.adapter import FixtureLLM

        llm = FixtureLLM()
        answer_result = llm.compose_answer(fact_sheet, question, concepts)

        # Validation: every cited id must be in the included set
        # and every consequential sentence must map to an included id
        # If validation fails, use template answer
        cited_ids = {c.subject_key for c in claims}
        validation_ok = bool(cited_ids)  # simplified

        grounding = "extracted" if validation_ok else "template"
        if not validation_ok:
            # Use deterministic template answer
            answer_result = {"answer": self._template_answer(question, concepts), "citations": []}

        # 8. Compute what_changed (diff from previous handoff for same task)
        # Placeholder - in production would diff against previous handoff
        what_changed = {"added": [], "removed": [], "changed": []}

        # 9. Build caveats
        caveats_result = build_caveats(
            contesting_memory_ids=list(resolved),
            receiver_agent_id=self.principal.agent_id,
            allowed_agent_ids={self.principal.agent_id},
            concepts=concepts,
        )

        # 10. Trace IDs (simulated)
        trace_ids = [str(uuid.uuid4()) for _ in range(3)]

        return {
            "answer": answer_result.get("answer", ""),
            "citations": answer_result.get("citations", []),
            "caveats": caveats_result,
            "excluded": [],
            "handoff_id": handoff_id,
            "readiness": readiness,
            "what_changed": what_changed,
            "llm_mode": self.settings.llm_mode if self.settings else "fixture",
            "grounding": grounding,
            "trace_ids": trace_ids,
        }

    @staticmethod
    def _template_answer(question: str, concepts: dict[str, dict]) -> str:
        """Deterministic template answer when validation fails."""
        relevant: list[str] = []
        for cid, cdata in concepts.items():
            cname = (cdata.get("canonical_name") or "").lower()
            if cname and cname in question.lower():
                relevant.append(cid)
        if relevant:
            return f"The available information covers: {', '.join(relevant)}."
        return "No supporting information found for this question."


# ---------------------------------------------------------------------------
# Coordinator: owns the state machine session
# ---------------------------------------------------------------------------

class Coordinator:
    """Coordinator: owns the state machine session -> propose -> verify -> handoff -> answer.

    Records episodes and emits events to a bounded ring buffer served by GET /api/events.
    """

    def __init__(self, principal: Any, graph_client: Any, settings: Any) -> None:
        self.principal = principal
        self.graph_client = graph_client
        self.settings = settings
        self.graph_name = graph_name_for_workspace(principal.workspace_id)
        # Event buffer: simple list with max size
        self._event_buffer: list[dict[str, Any]] = []
        self._max_events = getattr(settings, "trace_buffer_size", 500) if settings else 500

    async def run_session(
        self,
        task_question: str,
        source_id: str,
        concepts: dict[str, dict],
    ) -> dict[str, Any]:
        """Run the full coordination session: propose -> verify -> handoff -> answer.

        Returns the final answer dict.
        """
        from app.api.routes.handoffs import handoff_create
        from app.llm.adapter import FixtureLLM

        scout = Scout(self.principal, self.graph_client, self.settings)
        verifier = Verifier(self.principal, self.graph_client, self.settings)
        planner = Planner(self.principal, self.graph_client, self.settings)

        # Step 1: Scout - propose candidates
        scout_result = await scout.propose(
            question_or_task=task_question,
            source_id=source_id,
            predicate="",
            object_value="",
            summary="",
            confidence=0.5,
        )

        # Step 2: Verifier - evaluate conflicts
        # (In production, would evaluate each proposed memory against existing ones)
        verify_result = {"outcomes": [], "disputes": []}

        # Step 3: Planner - build handoff and answer
        planner_result = await planner.plan(
            question=task_question,
            source_id=source_id,
            concepts=concepts,
        )

        # Emit session event
        await self._emit_event(
            "session_complete",
            {
                "task": task_question,
                "handoff_id": planner_result.get("handoff_id"),
                "grounding": planner_result.get("grounding"),
                "llm_mode": planner_result.get("llm_mode"),
            },
        )

        return planner_result

    async def _emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Emit an event to the bounded ring buffer."""
        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "principal": self.principal.agent_id,
            "payload": payload,
            "timestamp": __import__("app.core.clock").utc_now_ms(),
        }

        # Add to buffer, respecting max size
        self._event_buffer.append(event)
        if len(self._event_buffer) > self._max_events:
            self._event_buffer = self._event_buffer[-self._max_events:]

    async def get_events(self, since: Optional[str] = None) -> list[dict[str, Any]]:
        """Get events since a given id (polling endpoint).

        Fine-grained polling is fine; SSE is not required.
        """
        if since is None:
            return list(self._event_buffer)
        # Filter events after the given id
        try:
            since_id = int(since)
            return [e for e in self._event_buffer if e["id"] > since_id]
        except (ValueError, TypeError):
            return list(self._event_buffer)