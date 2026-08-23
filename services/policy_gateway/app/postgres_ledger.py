"""PostgreSQL-backed, tenant-scoped single-use authorization ledger."""
import hashlib


class PostgresReplayLedger:
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

    def register(self, jti: str, claims, token_hash: str):
        nonce_hash = hashlib.sha256(jti.encode()).hexdigest()
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (claims.tenant_id,))
                cursor.execute(
                    """INSERT INTO outbound_authorization
                       (id, tenant_id, decision_id, channel, nonce_hash, token_hash, issued_at, expires_at)
                       VALUES (%s, %s, %s, %s, %s, %s, to_timestamp(%s), to_timestamp(%s))""",
                    (jti, claims.tenant_id, claims.decision_id, claims.channel, nonce_hash, token_hash, claims.iat, claims.exp),
                )

    def consume(self, jti: str, claims) -> bool:
        nonce_hash = hashlib.sha256(jti.encode()).hexdigest()
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (claims.tenant_id,))
                cursor.execute(
                    """UPDATE outbound_authorization
                       SET consumed_at = now()
                       WHERE tenant_id = %s AND nonce_hash = %s AND consumed_at IS NULL
                         AND revoked_at IS NULL AND expires_at > now()
                       RETURNING id""",
                    (claims.tenant_id, nonce_hash),
                )
                return cursor.fetchone() is not None
