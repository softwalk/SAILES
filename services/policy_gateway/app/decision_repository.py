"""Persist policy decisions required by the PostgreSQL authorization ledger."""
import json
from datetime import timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from atlantis_contracts import DecisionOutcome


class PostgresDecisionRepository:
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
    def action_intent_id(decision_id: str) -> str:
        """Return a stable ID so retries cannot create orphan action intents."""
        return str(uuid5(NAMESPACE_URL, f"atlantis:action-intent:{decision_id}"))

    def persist(self, decision, request) -> str:
        intent_id = self.action_intent_id(decision.decision_id)
        status = {
            DecisionOutcome.ALLOW: "ALLOWED",
            DecisionOutcome.DENY: "DENIED",
            DecisionOutcome.REVIEW: "REVIEW",
        }[decision.outcome]
        expires_at = decision.decided_at + timedelta(minutes=5)
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    (request.tenant_id,),
                )
                cursor.execute(
                    """INSERT INTO action_intent
                       (id, tenant_id, contact_id, campaign_version_id, purpose, channel,
                        content_hash, workflow_version, status, requested_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (id) DO NOTHING""",
                    (
                        intent_id, request.tenant_id, request.contact_id,
                        request.campaign_version_id, request.purpose, request.channel.value,
                        request.content_hash, "sales-graph@1", status, request.requested_at,
                    ),
                )
                cursor.execute(
                    """INSERT INTO contactability_decision
                       (id, tenant_id, contact_id, campaign_version_id, channel, purpose,
                        result, reason_codes, evidence_ids, policy_version, content_hash,
                        decided_at, expires_at, action_intent_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s)
                       ON CONFLICT (id) DO NOTHING""",
                    (
                        decision.decision_id, request.tenant_id, request.contact_id,
                        request.campaign_version_id, request.channel.value, request.purpose,
                        decision.outcome.value, json.dumps(list(decision.reason_codes)),
                        json.dumps(decision.evidence.get("evidence_ids", [])),
                        decision.policy_version, request.content_hash, decision.decided_at,
                        expires_at, intent_id,
                    ),
                )
                correlation_id = request.metadata.get("correlation_id") or decision.decision_id
                try:
                    correlation_id = str(UUID(str(correlation_id)))
                except (ValueError, TypeError, AttributeError):
                    correlation_id = decision.decision_id
                cursor.execute(
                    """SELECT app.append_audit_event(%s,'SERVICE','policy-gateway','POLICY_DECIDED',
                              'CONTACTABILITY_DECISION',%s,%s,%s::jsonb,%s)""",
                    (request.tenant_id, decision.decision_id, decision.decision_id,
                     json.dumps(list(decision.reason_codes)), correlation_id),
                )
        return intent_id
