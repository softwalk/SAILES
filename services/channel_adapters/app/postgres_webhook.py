from uuid import uuid4


class PostgresWebhookInbox:
    def __init__(self, connection_factory, tenant_id: str):
        self.connection_factory, self.tenant_id = connection_factory, tenant_id

    @classmethod
    def from_dsn(cls, dsn: str, tenant_id: str):
        def factory():
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("PSYCOPG_NOT_INSTALLED_FROM_APPROVED_LOCK") from exc
            return psycopg.connect(dsn)
        return cls(factory, tenant_id)

    def remember(self, provider: str, event_id: str, body_hash: str) -> bool:
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (self.tenant_id,))
                cursor.execute(
                    """INSERT INTO webhook_receipt
                       (id, tenant_id, provider, provider_event_id, body_hash, signature_valid, status, correlation_id)
                       VALUES (%s,%s,%s,%s,%s,true,'RECEIVED',%s)
                       ON CONFLICT (tenant_id, provider, provider_event_id) DO NOTHING RETURNING id""",
                    (str(uuid4()), self.tenant_id, provider, event_id, body_hash, str(uuid4())),
                )
                return cursor.fetchone() is not None
