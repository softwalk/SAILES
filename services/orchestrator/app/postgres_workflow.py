"""Transactional PostgreSQL workflow state used by the HTTP orchestrator."""
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlantis_contracts import sha256_hex
from .workflow import SalesRunState, Stage, WorkflowEngine


class PostgresWorkflowRepository:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @classmethod
    def from_dsn(cls, dsn: str):
        def factory():
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("PSYCOPG_NOT_INSTALLED_FROM_APPROVED_LOCK") from exc
            return psycopg.connect(dsn)
        return cls(factory)

    @staticmethod
    def _set_tenant(cursor, tenant_id: str):
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))

    @staticmethod
    def _state_payload(state: SalesRunState) -> dict:
        payload = asdict(state)
        payload["stage"] = state.stage.value
        return payload

    @classmethod
    def _state_from_payload(cls, payload: dict) -> SalesRunState:
        value = dict(payload)
        value["stage"] = Stage(value["stage"])
        value["facts"] = tuple(value.get("facts", ()))
        return SalesRunState(**value)

    @classmethod
    def _checkpoint(cls, cursor, state: SalesRunState) -> SalesRunState:
        state = replace(state, checkpoint_no=state.checkpoint_no + 1)
        payload = cls._state_payload(state)
        digest = sha256_hex(payload)
        cursor.execute(
            """INSERT INTO graph_checkpoint
               (run_id,checkpoint_no,tenant_id,state,state_hash,workflow_version)
               VALUES (%s,%s,%s,%s::jsonb,%s,%s)""",
            (state.run_id, state.checkpoint_no, state.tenant_id, json.dumps(payload), digest, state.workflow_version),
        )
        cursor.execute(
            """UPDATE graph_run SET stage=%s,status=%s,workflow_version=%s,
               state_schema_version=%s,version=version+1,updated_at=now()
               WHERE tenant_id=%s AND id=%s""",
            (state.stage.value, state.status, state.workflow_version, state.schema_version, state.tenant_id, state.run_id),
        )
        return state

    @classmethod
    def _locked_state(cls, cursor, tenant_id: str, run_id: str) -> SalesRunState:
        cursor.execute(
            "SELECT id FROM graph_run WHERE tenant_id=%s AND id=%s FOR UPDATE",
            (tenant_id, run_id),
        )
        if cursor.fetchone() is None:
            raise ValueError("RUN_NOT_FOUND")
        cursor.execute(
            """SELECT gc.state,gc.state_hash FROM graph_checkpoint gc
               WHERE gc.tenant_id=%s AND gc.run_id=%s
               ORDER BY gc.checkpoint_no DESC LIMIT 1 FOR UPDATE""",
            (tenant_id, run_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("RUN_NOT_FOUND")
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if sha256_hex(payload) != row[1]:
            raise ValueError("CHECKPOINT_HASH_INVALID")
        return cls._state_from_payload(payload)

    @staticmethod
    def _audit(cursor, tenant_id: str, actor_type: str, actor_id: str, action: str,
               resource_type: str, resource_id: str, correlation_id: str, reasons=None):
        cursor.execute(
            "SELECT app.append_audit_event(%s,%s,%s,%s,%s,%s,NULL,%s::jsonb,%s)",
            (tenant_id, actor_type, actor_id, action, resource_type, resource_id,
             json.dumps(reasons or []), correlation_id),
        )

    def start(self, tenant_id: str, campaign_version_id: str, contact_id: str) -> SalesRunState:
        run_id = str(uuid4())
        state = SalesRunState(tenant_id, run_id, campaign_version_id, contact_id)
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._set_tenant(cursor, tenant_id)
                cursor.execute(
                    """INSERT INTO graph_run
                       (id,tenant_id,contact_id,campaign_version_id,stage,status,state_schema_version,
                        correlation_id,workflow_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (run_id, tenant_id, contact_id, campaign_version_id, state.stage.value, state.status,
                     state.schema_version, run_id, state.workflow_version),
                )
                state = self._checkpoint(cursor, state)
                self._audit(cursor, tenant_id, "SERVICE", "orchestrator", "RUN_STARTED", "GRAPH_RUN", run_id, run_id)
        return state

    def get(self, tenant_id: str, run_id: str) -> SalesRunState:
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._set_tenant(cursor, tenant_id)
                return self._locked_state(cursor, tenant_id, run_id)

    def transition(self, tenant_id: str, run_id: str, event_id: str, payload: dict | None = None) -> SalesRunState:
        payload = payload or {}
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._set_tenant(cursor, tenant_id)
                state = self._locked_state(cursor, tenant_id, run_id)
                cursor.execute(
                    """INSERT INTO workflow_event (tenant_id,run_id,event_id,event_type)
                       VALUES (%s,%s,%s,'TRANSITION') ON CONFLICT DO NOTHING RETURNING event_id""",
                    (tenant_id, run_id, event_id),
                )
                if cursor.fetchone() is None:
                    return state
                if state.status != "RUNNING":
                    raise ValueError("RUN_NOT_ACTIVE")
                index = WorkflowEngine.order.index(state.stage)
                if state.stage == Stage.APPROVE:
                    subject_hash = str(payload.get("subject_hash", ""))
                    if len(subject_hash) != 64:
                        raise ValueError("HUMAN_ACTION_SUBJECT_HASH_REQUIRED")
                    action_id = str(uuid4())
                    expires_at = datetime.now(UTC) + timedelta(hours=24)
                    cursor.execute(
                        """INSERT INTO human_action
                           (id,tenant_id,run_id,subject_type,subject_id,subject_hash,reason_code,
                            required_role,status,expires_at)
                           VALUES (%s,%s,%s,'CAMPAIGN_VERSION',%s,%s,'CAMPAIGN_EXECUTION_APPROVAL',
                                   'HUMAN_REVIEWER','PENDING',%s)""",
                        (action_id, tenant_id, run_id, state.campaign_version_id, subject_hash, expires_at),
                    )
                    updated = replace(state, status="WAITING_HUMAN", pending_human_action_id=action_id,
                                      last_event_id=event_id)
                    self._audit(cursor, tenant_id, "SERVICE", "orchestrator", "HUMAN_ACTION_CREATED",
                                "HUMAN_ACTION", action_id, run_id)
                else:
                    next_stage = WorkflowEngine.order[min(index + 1, len(WorkflowEngine.order) - 1)]
                    updated = replace(state, stage=next_stage, last_event_id=event_id)
                updated = self._checkpoint(cursor, updated)
                self._audit(cursor, tenant_id, "SERVICE", "orchestrator", "RUN_TRANSITIONED",
                            "GRAPH_RUN", run_id, run_id, [updated.stage.value, updated.status])
                return updated

    def decide_human_action(self, tenant_id: str, run_id: str, action_id: str, approved: bool,
                            actor_id: str, subject_hash: str, comment: str | None = None) -> SalesRunState:
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._set_tenant(cursor, tenant_id)
                state = self._locked_state(cursor, tenant_id, run_id)
                cursor.execute(
                    """SELECT status,subject_hash,expires_at FROM human_action
                       WHERE tenant_id=%s AND id=%s AND run_id=%s FOR UPDATE""",
                    (tenant_id, action_id, run_id),
                )
                row = cursor.fetchone()
                if row is None or row[0] != "PENDING":
                    raise ValueError("HUMAN_ACTION_NOT_PENDING")
                if row[2] <= datetime.now(UTC):
                    cursor.execute(
                        "UPDATE human_action SET status='EXPIRED',updated_at=now(),version=version+1 WHERE tenant_id=%s AND id=%s",
                        (tenant_id, action_id),
                    )
                    updated = self._checkpoint(cursor, replace(
                        state, status="BLOCKED", pending_human_action_id=None,
                    ))
                    self._audit(cursor, tenant_id, "SYSTEM", "orchestrator", "HUMAN_ACTION_EXPIRED",
                                "HUMAN_ACTION", action_id, run_id)
                    return updated
                if row[1] != subject_hash:
                    raise ValueError("HUMAN_ACTION_HASH_MISMATCH")
                decision = "APPROVED" if approved else "REJECTED"
                cursor.execute(
                    """UPDATE human_action SET status=%s,decision_comment=%s,decided_by=%s,
                       decided_at=now(),updated_at=now(),version=version+1
                       WHERE tenant_id=%s AND id=%s""",
                    (decision, comment, actor_id, tenant_id, action_id),
                )
                if approved:
                    updated = replace(state, status="RUNNING", stage=Stage.CONTACT, pending_human_action_id=None)
                else:
                    updated = replace(state, status="BLOCKED", pending_human_action_id=None)
                updated = self._checkpoint(cursor, updated)
                self._audit(cursor, tenant_id, "USER", actor_id, "HUMAN_ACTION_" + decision,
                            "HUMAN_ACTION", action_id, run_id)
                return updated
