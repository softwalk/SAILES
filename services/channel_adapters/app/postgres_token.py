"""Atomic JIT token consumer colocated with channel adapters."""
import hashlib


class PostgresTokenConsumer:
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

    def consume(self, jti: str, claims) -> bool:
        nonce_hash = hashlib.sha256(jti.encode()).hexdigest()
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (claims.tenant_id,))
                cursor.execute(
                    """UPDATE outbound_authorization SET consumed_at=now()
                       WHERE tenant_id=%s AND nonce_hash=%s AND consumed_at IS NULL
                         AND revoked_at IS NULL AND expires_at > now()
                       RETURNING id""",
                    (claims.tenant_id, nonce_hash),
                )
                return cursor.fetchone() is not None


class ShadowFirstUseConsumer:
    """Local-only fallback. Forbidden when shadow mode is disabled."""
    def __init__(self): self.seen = set()

    def consume(self, jti, claims=None):
        if jti in self.seen:
            return False
        self.seen.add(jti)
        return True
