"""Production PostgreSQL repository. Imports psycopg only when configured."""
import json
from contextlib import contextmanager
from uuid import uuid4


class PostgresCRMRepository:
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

    @contextmanager
    def _cursor(self, tenant_id: str):
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
                yield cursor

    def create_contact(self, tenant_id: str, data: dict) -> dict:
        contact_id = data.get("id", str(uuid4()))
        with self._cursor(tenant_id) as cursor:
            cursor.execute(
                """INSERT INTO contact (id, tenant_id, display_name, company_name, phone_token, lifecycle_stage)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id, tenant_id, display_name, company_name, phone_token, lifecycle_stage, version""",
                (contact_id, tenant_id, data.get("display_name"), data.get("company_name"),
                 data.get("phone_token"), data.get("lifecycle_stage", "DISCOVERED")),
            )
            return self._row(cursor)

    def grant_consent(self, tenant_id: str, data: dict) -> dict:
        consent_id = str(uuid4())
        with self._cursor(tenant_id) as cursor:
            cursor.execute(
                """INSERT INTO consent_ledger
                   (id, tenant_id, contact_id, channel, purpose, status, capture_source,
                    notice_version, evidence_uri, evidence_hash, captured_at, valid_until)
                   VALUES (%s,%s,%s,%s,%s,'GRANTED',%s,%s,%s,%s,%s,%s)
                   RETURNING id, tenant_id, contact_id, channel, purpose, status, evidence_hash""",
                (consent_id, tenant_id, data["contact_id"], data["channel"], data["purpose"],
                 data["capture_source"], data.get("notice_version"), data.get("evidence_uri"),
                 data["evidence_hash"], data["captured_at"], data.get("valid_until")),
            )
            return self._row(cursor)

    def suppress(self, tenant_id: str, data: dict) -> dict:
        if data.get("scope", "TENANT") == "GLOBAL":
            raise PermissionError("GLOBAL_SUPPRESSION_REQUIRES_ADMIN_ROLE")
        suppression_id = str(uuid4())
        with self._cursor(tenant_id) as cursor:
            cursor.execute(
                """INSERT INTO suppression
                   (id, tenant_id, contact_id, phone_token, channel, purpose, scope, reason, source, expires_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id, tenant_id, contact_id, channel, purpose, scope, reason, effective_at""",
                (suppression_id, tenant_id, data.get("contact_id"), data.get("phone_token"),
                 data.get("channel"), data.get("purpose"), data.get("scope", "TENANT"),
                 data.get("reason", "OPT_OUT"), data.get("source", "API"), data.get("expires_at")),
            )
            return self._row(cursor)

    def contactability_evidence(self, tenant_id: str, contact_id: str, phone_token: str, channel: str, purpose: str,
                                campaign_version_id: str) -> dict:
        with self._cursor(tenant_id) as cursor:
            cursor.execute(
                """SELECT
                     EXISTS(SELECT 1 FROM suppression s WHERE
                       (s.tenant_id = %s OR s.tenant_id IS NULL)
                       AND (s.contact_id = %s OR s.phone_token = %s)
                       AND (s.expires_at IS NULL OR s.expires_at > now())) AS suppressed,
                     EXISTS(SELECT 1 FROM consent_ledger c WHERE c.tenant_id=%s AND c.contact_id=%s
                       AND c.channel=%s AND c.purpose=%s AND c.status='GRANTED'
                       AND (c.valid_until IS NULL OR c.valid_until > now())) AS consent_active,
                     EXISTS(SELECT 1 FROM campaign_version cv JOIN approval a
                       ON a.tenant_id=cv.tenant_id AND a.subject_id=cv.id AND a.subject_hash=cv.artifact_hash AND a.decision='APPROVE'
                       WHERE cv.tenant_id=%s AND cv.id=%s AND cv.status IN ('APPROVED','RUNNING')) AS campaign_approved,
                     (SELECT ca.canonical_manifest->'content_hashes'->>lower(%s)
                       FROM campaign_artifact ca WHERE ca.tenant_id=%s AND ca.campaign_version_id=%s
                       ORDER BY ca.created_at DESC LIMIT 1) AS approved_content_hash,
                     COALESCE((SELECT (ca.canonical_manifest->'repep'->>'enabled')::boolean
                       FROM campaign_artifact ca WHERE ca.tenant_id=%s AND ca.campaign_version_id=%s
                       ORDER BY ca.created_at DESC LIMIT 1), false) AS repep_enabled,
                     (SELECT ca.canonical_manifest->'repep'->>'exemption_type'
                       FROM campaign_artifact ca WHERE ca.tenant_id=%s AND ca.campaign_version_id=%s
                       ORDER BY ca.created_at DESC LIMIT 1) AS repep_exemption_type,
                     COALESCE((SELECT (ca.canonical_manifest->'repep'->>'exemption_approved')::boolean
                       FROM campaign_artifact ca WHERE ca.tenant_id=%s AND ca.campaign_version_id=%s
                       ORDER BY ca.created_at DESC LIMIT 1), false) AS repep_exemption_approved,
                     (SELECT ca.canonical_manifest->'repep'->>'exemption_evidence_ref'
                       FROM campaign_artifact ca WHERE ca.tenant_id=%s AND ca.campaign_version_id=%s
                       ORDER BY ca.created_at DESC LIMIT 1) AS repep_exemption_evidence_ref""",
                (tenant_id, contact_id, phone_token, tenant_id, contact_id, channel, purpose,
                 tenant_id, campaign_version_id, channel, tenant_id, campaign_version_id,
                 tenant_id, campaign_version_id, tenant_id, campaign_version_id,
                 tenant_id, campaign_version_id, tenant_id, campaign_version_id),
            )
            row = self._row(cursor)
            cursor.execute(
                """SELECT result, valid_until, snapshot_id FROM repep_check
                   WHERE tenant_id=%s AND phone_token=%s AND valid_until > now()
                   ORDER BY checked_at DESC LIMIT 1""",
                (tenant_id, phone_token),
            )
            repep = cursor.fetchone()
            row.update(repep_snapshot_valid=bool(repep), repep_listed=None if not repep else repep[0] != "NOT_LISTED")
            return row

    def record_interaction(self, tenant_id: str, contact_id: str, data: dict) -> dict:
        interaction_id = data.get("id", str(uuid4()))
        with self._cursor(tenant_id) as cursor:
            cursor.execute(
                """INSERT INTO interaction
                   (id,tenant_id,contact_id,campaign_version_id,channel,provider,provider_ref,direction,status,
                    content_uri,content_hash,started_at,ended_at,correlation_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (tenant_id,provider,provider_ref) DO UPDATE SET status=EXCLUDED.status, ended_at=EXCLUDED.ended_at
                   RETURNING id,tenant_id,contact_id,channel,provider,provider_ref,direction,status,correlation_id""",
                (interaction_id,tenant_id,contact_id,data.get("campaign_version_id"),data["channel"],data["provider"],
                 data.get("provider_ref"),data["direction"],data["status"],data.get("content_uri"),data.get("content_hash"),
                 data.get("started_at"),data.get("ended_at"),data["correlation_id"]),
            )
            return self._row(cursor)

    def upsert_opportunity(self, tenant_id: str, contact_id: str, data: dict) -> dict:
        opportunity_id = data.get("id", str(uuid4()))
        with self._cursor(tenant_id) as cursor:
            cursor.execute(
                """INSERT INTO opportunity (id,tenant_id,contact_id,stage,amount,currency,sensitivity,owner_user_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                   ON CONFLICT (id) DO UPDATE SET stage=EXCLUDED.stage,amount=EXCLUDED.amount,
                     currency=EXCLUDED.currency,sensitivity=EXCLUDED.sensitivity,version=opportunity.version+1,updated_at=now()
                   RETURNING id,tenant_id,contact_id,stage,amount,currency,sensitivity,version""",
                (opportunity_id,tenant_id,contact_id,data["stage"],data.get("amount"),data.get("currency"),
                 json.dumps(data.get("sensitivity", {})),data.get("owner_user_id")),
            )
            return self._row(cursor)

    def add_memory_fact(self, tenant_id: str, contact_id: str, fact: dict) -> dict:
        fact_id = str(uuid4())
        with self._cursor(tenant_id) as cursor:
            cursor.execute(
                """INSERT INTO memory_fact
                   (id,tenant_id,contact_id,predicate,value,fact_kind,source_interaction_id,confidence,classification,valid_from,valid_until)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s)
                   RETURNING id,tenant_id,contact_id,predicate,value,fact_kind,confidence,classification,valid_from,valid_until""",
                (fact_id,tenant_id,contact_id,fact["predicate"],json.dumps(fact["value"]),fact["fact_kind"],
                 fact.get("source_interaction_id"),fact["confidence"],fact["classification"],fact["valid_from"],fact.get("valid_until")),
            )
            return self._row(cursor)

    def request_arco(self, tenant_id: str, contact_id: str, request_type: str, verification_ref: str) -> dict:
        request_id = str(uuid4())
        with self._cursor(tenant_id) as cursor:
            cursor.execute(
                """INSERT INTO data_subject_request
                   (id,tenant_id,contact_id,request_type,identity_verification_ref,status,due_at)
                   VALUES (%s,%s,%s,%s,%s,'OPEN',now()+interval '20 days')
                   RETURNING id,tenant_id,contact_id,request_type,status,due_at""",
                (request_id,tenant_id,contact_id,request_type,verification_ref),
            )
            return self._row(cursor)

    @staticmethod
    def _row(cursor):
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("DATABASE_WRITE_RETURNED_NO_ROW")
        columns = [column.name if hasattr(column, "name") else column[0] for column in cursor.description]
        return dict(zip(columns, row))
