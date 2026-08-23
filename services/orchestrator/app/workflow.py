from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import RLock
from uuid import uuid4

from atlantis_contracts import sha256_hex


class Stage(StrEnum):
    QUALIFY = "QUALIFY"
    PREPARE = "PREPARE"
    APPROVE = "APPROVE"
    CONTACT = "CONTACT"
    CONVERSE = "CONVERSE"
    HANDOFF = "HANDOFF"
    CLOSE = "CLOSE"


@dataclass(frozen=True)
class SalesRunState:
    tenant_id: str
    run_id: str
    campaign_version_id: str
    contact_id: str
    stage: Stage = Stage.QUALIFY
    status: str = "RUNNING"
    facts: tuple[dict, ...] = ()
    policy_decision_id: str | None = None
    pending_human_action_id: str | None = None
    attempts: dict[str, int] = field(default_factory=dict)
    last_event_id: str | None = None
    next_action: dict = field(default_factory=dict)
    schema_version: int = 1
    workflow_version: str = "sales-graph@1"
    checkpoint_no: int = 0


class WorkflowEngine:
    """Deterministic LangGraph-compatible state engine for replay and offline tests."""

    order = [Stage.QUALIFY, Stage.PREPARE, Stage.APPROVE, Stage.CONTACT, Stage.CONVERSE, Stage.HANDOFF, Stage.CLOSE]

    def __init__(self):
        self._lock = RLock()
        self.checkpoints: dict[str, list[dict]] = {}
        self.outbox: dict[str, dict] = {}
        self.processed_events: set[str] = set()
        self.human_actions: dict[str, dict] = {}

    def start(self, tenant_id: str, campaign_version_id: str, contact_id: str) -> SalesRunState:
        with self._lock:
            state = SalesRunState(tenant_id, str(uuid4()), campaign_version_id, contact_id)
            return self._checkpoint(state)

    def transition(self, state: SalesRunState, event_id: str, payload: dict | None = None) -> SalesRunState:
        with self._lock:
            return self._transition_unlocked(state, event_id, payload)

    def _transition_unlocked(self, state: SalesRunState, event_id: str, payload: dict | None = None) -> SalesRunState:
        if event_id in self.processed_events:
            return state
        if state.status != "RUNNING":
            raise ValueError("RUN_NOT_ACTIVE")
        payload = payload or {}
        self.processed_events.add(event_id)
        index = self.order.index(state.stage)
        if state.stage == Stage.APPROVE:
            action_id = str(uuid4())
            self.human_actions[action_id] = {
                "id": action_id, "status": "PENDING", "subject_hash": payload.get("subject_hash"),
                "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            }
            next_state = replace(state, status="WAITING_HUMAN", pending_human_action_id=action_id, last_event_id=event_id)
        else:
            next_stage = self.order[min(index + 1, len(self.order) - 1)]
            next_state = replace(state, stage=next_stage, last_event_id=event_id)
        return self._checkpoint(next_state)

    def decide_human_action(self, state: SalesRunState, action_id: str, approved: bool, actor_id: str, subject_hash: str) -> SalesRunState:
        with self._lock:
            return self._decide_human_action_unlocked(state, action_id, approved, actor_id, subject_hash)

    def _decide_human_action_unlocked(self, state: SalesRunState, action_id: str, approved: bool, actor_id: str, subject_hash: str) -> SalesRunState:
        action = self.human_actions.get(action_id)
        if not action or action["status"] != "PENDING":
            raise ValueError("HUMAN_ACTION_NOT_PENDING")
        if action["subject_hash"] != subject_hash:
            raise ValueError("HUMAN_ACTION_HASH_MISMATCH")
        action.update(status="APPROVED" if approved else "REJECTED", actor_id=actor_id)
        if not approved:
            return self._checkpoint(replace(state, status="BLOCKED", pending_human_action_id=None))
        return self._checkpoint(replace(state, status="RUNNING", stage=Stage.CONTACT, pending_human_action_id=None))

    def expire_human_actions(self, states: dict[str, SalesRunState], now=None) -> list[SalesRunState]:
        with self._lock:
            return self._expire_human_actions_unlocked(states, now)

    def _expire_human_actions_unlocked(self, states: dict[str, SalesRunState], now=None) -> list[SalesRunState]:
        clock = datetime.now(UTC) if now is None else now
        changed = []
        for run_id, state in list(states.items()):
            action = self.human_actions.get(state.pending_human_action_id or "")
            if action and action["status"] == "PENDING" and datetime.fromisoformat(action["expires_at"]) <= clock:
                action["status"] = "EXPIRED"
                updated = self._checkpoint(replace(state, status="BLOCKED", pending_human_action_id=None))
                states[run_id] = updated
                changed.append(updated)
        return changed

    def cancel_pending_effects(self, run_id: str, reason: str) -> int:
        with self._lock:
            return self._cancel_pending_effects_unlocked(run_id, reason)

    def _cancel_pending_effects_unlocked(self, run_id: str, reason: str) -> int:
        count = 0
        for key, item in self.outbox.items():
            if item["run_id"] == run_id and item["status"] == "PENDING":
                self.outbox[key] = {**item, "status": "CANCELLED", "cancel_reason": reason}
                count += 1
        return count

    def enqueue_effect(self, state: SalesRunState, effect: dict, idempotency_key: str) -> dict:
        with self._lock:
            return self._enqueue_effect_unlocked(state, effect, idempotency_key)

    def _enqueue_effect_unlocked(self, state: SalesRunState, effect: dict, idempotency_key: str) -> dict:
        existing = self.outbox.get(idempotency_key)
        if existing:
            return existing
        item = {"id": str(uuid4()), "tenant_id": state.tenant_id, "run_id": state.run_id,
                "idempotency_key": idempotency_key, "effect": effect, "status": "PENDING"}
        self.outbox[idempotency_key] = item
        return item

    def _checkpoint(self, state: SalesRunState) -> SalesRunState:
        state = replace(state, checkpoint_no=state.checkpoint_no + 1)
        body = asdict(state)
        body["state_hash"] = sha256_hex(body)
        self.checkpoints.setdefault(state.run_id, []).append(body)
        return state

    def restore(self, checkpoints: list[dict]) -> SalesRunState:
        with self._lock:
            return self._restore_unlocked(checkpoints)

    def _restore_unlocked(self, checkpoints: list[dict]) -> SalesRunState:
        if not checkpoints: raise ValueError("CHECKPOINTS_REQUIRED")
        previous_no = 0
        for checkpoint in checkpoints:
            body = dict(checkpoint)
            supplied_hash = body.pop("state_hash", None)
            if supplied_hash != sha256_hex(body): raise ValueError("CHECKPOINT_HASH_INVALID")
            if body["checkpoint_no"] != previous_no + 1: raise ValueError("CHECKPOINT_SEQUENCE_INVALID")
            if body["workflow_version"] != "sales-graph@1": raise ValueError("WORKFLOW_VERSION_UNAVAILABLE")
            previous_no = body["checkpoint_no"]
        last = dict(checkpoints[-1]); last.pop("state_hash")
        last["stage"] = Stage(last["stage"])
        last["facts"] = tuple(last.get("facts", ()))
        state = SalesRunState(**last)
        self.checkpoints[state.run_id] = [dict(item) for item in checkpoints]
        return state
