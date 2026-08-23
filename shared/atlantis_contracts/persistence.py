"""Durable and bounded stores for replay protection and HTTP idempotency."""
import json
import os
import time
from dataclasses import asdict, is_dataclass
from threading import RLock

from .config import postgres_dsn


def _json_value(value):
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class BoundedTTLMap:
    def __init__(self, ttl_seconds=86_400, max_entries=10_000, clock=time.monotonic):
        self.ttl_seconds, self.max_entries, self.clock = ttl_seconds, max_entries, clock
        self._values, self._lock = {}, RLock()

    def __setitem__(self, key, value):
        now = self.clock()
        with self._lock:
            self._prune(now)
            if len(self._values) >= self.max_entries and key not in self._values:
                oldest = min(self._values, key=lambda item: self._values[item][1])
                self._values.pop(oldest, None)
            self._values[key] = (value, now + self.ttl_seconds)

    def __getitem__(self, key):
        now = self.clock()
        with self._lock:
            self._prune(now)
            return self._values[key][0]

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def _prune(self, now):
        for key in [key for key, value in self._values.items() if value[1] <= now]:
            self._values.pop(key, None)


class BoundedTTLSet:
    def __init__(self, ttl_seconds=86_400, max_entries=20_000, clock=time.monotonic):
        self._map = BoundedTTLMap(ttl_seconds, max_entries, clock)
        self._lock = RLock()

    def remember(self, value) -> bool:
        with self._lock:
            if self._map.get(value) is not None:
                return False
            self._map[value] = True
            return True


class MemoryNonceStore:
    def __init__(self, ttl_seconds=120, max_entries=20_000, clock=time.monotonic):
        self.ttl_seconds, self.max_entries, self.clock = ttl_seconds, max_entries, clock
        self._values, self._lock = {}, RLock()

    def remember(self, service_id: str, nonce: str, tenant_id: str, issued_at: int) -> bool:
        now = self.clock()
        key = tenant_id, service_id, nonce
        with self._lock:
            self._values = {k: expiry for k, expiry in self._values.items() if expiry > now}
            if key in self._values:
                return False
            if len(self._values) >= self.max_entries:
                oldest = min(self._values, key=self._values.get)
                self._values.pop(oldest, None)
            self._values[key] = now + self.ttl_seconds
            return True


class PostgresNonceStore:
    def __init__(self, connection_factory, ttl_seconds=120):
        self.connection_factory, self.ttl_seconds = connection_factory, ttl_seconds

    @classmethod
    def from_dsn(cls, dsn: str, ttl_seconds=120):
        def factory():
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("PSYCOPG_NOT_INSTALLED_FROM_APPROVED_LOCK") from exc
            return psycopg.connect(dsn)
        return cls(factory, ttl_seconds)

    def remember(self, service_id: str, nonce: str, tenant_id: str, issued_at: int) -> bool:
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
                cursor.execute(
                    "DELETE FROM workload_nonce WHERE tenant_id=%s AND expires_at <= now()",
                    (tenant_id,),
                )
                cursor.execute(
                    """INSERT INTO workload_nonce (tenant_id,service_id,nonce,issued_at,expires_at)
                       VALUES (%s,%s,%s,to_timestamp(%s),to_timestamp(%s))
                       ON CONFLICT (tenant_id,service_id,nonce) DO NOTHING RETURNING nonce""",
                    (tenant_id, service_id, nonce, issued_at, issued_at + self.ttl_seconds),
                )
                return cursor.fetchone() is not None


class MemoryIdempotencyStore:
    def __init__(self, service_name: str, ttl_seconds=86_400, max_entries=10_000, clock=time.monotonic):
        self.service_name = service_name
        self.ttl_seconds, self.max_entries, self.clock = ttl_seconds, max_entries, clock
        self._values, self._lock = {}, RLock()

    def claim(self, tenant_id: str, key: str, request_hash: str):
        now = self.clock()
        cache_key = tenant_id, self.service_name, key
        with self._lock:
            self._values = {k: v for k, v in self._values.items() if v[3] > now}
            existing = self._values.get(cache_key)
            if existing:
                if existing[0] != request_hash:
                    return "CONFLICT", None
                if existing[1] is None:
                    return "PENDING", None
                return "CACHED", (existing[1], existing[2])
            if len(self._values) >= self.max_entries:
                oldest = min(self._values, key=lambda item: self._values[item][3])
                self._values.pop(oldest, None)
            self._values[cache_key] = (request_hash, None, None, now + self.ttl_seconds)
            return "NEW", None

    def finish(self, tenant_id: str, key: str, request_hash: str, status: int, body):
        cache_key = tenant_id, self.service_name, key
        with self._lock:
            current = self._values.get(cache_key)
            if current and current[0] == request_hash:
                self._values[cache_key] = (request_hash, status, body, current[3])

    def abandon(self, tenant_id: str, key: str, request_hash: str):
        cache_key = tenant_id, self.service_name, key
        with self._lock:
            current = self._values.get(cache_key)
            if current and current[0] == request_hash and current[1] is None:
                self._values.pop(cache_key, None)


class PostgresIdempotencyStore:
    def __init__(self, connection_factory, service_name: str, ttl_seconds=86_400):
        self.connection_factory, self.service_name, self.ttl_seconds = connection_factory, service_name, ttl_seconds

    @classmethod
    def from_dsn(cls, dsn: str, service_name: str, ttl_seconds=86_400):
        def factory():
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("PSYCOPG_NOT_INSTALLED_FROM_APPROVED_LOCK") from exc
            return psycopg.connect(dsn)
        return cls(factory, service_name, ttl_seconds)

    def _tenant(self, cursor, tenant_id):
        cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))

    def claim(self, tenant_id: str, key: str, request_hash: str):
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._tenant(cursor, tenant_id)
                cursor.execute(
                    """DELETE FROM idempotency_record
                       WHERE tenant_id=%s AND service_name=%s AND idempotency_key=%s AND expires_at <= now()""",
                    (tenant_id, self.service_name, key),
                )
                cursor.execute(
                    """INSERT INTO idempotency_record
                       (tenant_id,service_name,idempotency_key,request_hash,expires_at)
                       VALUES (%s,%s,%s,%s,now()+(%s * interval '1 second'))
                       ON CONFLICT DO NOTHING RETURNING idempotency_key""",
                    (tenant_id, self.service_name, key, request_hash, self.ttl_seconds),
                )
                if cursor.fetchone() is not None:
                    return "NEW", None
                cursor.execute(
                    """SELECT request_hash,response_status,response_body FROM idempotency_record
                       WHERE tenant_id=%s AND service_name=%s AND idempotency_key=%s""",
                    (tenant_id, self.service_name, key),
                )
                existing = cursor.fetchone()
                if not existing or existing[0] != request_hash:
                    return "CONFLICT", None
                if existing[1] is None:
                    return "PENDING", None
                return "CACHED", (existing[1], existing[2])

    def finish(self, tenant_id: str, key: str, request_hash: str, status: int, body):
        payload = json.dumps(body, default=_json_value, separators=(",", ":"))
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._tenant(cursor, tenant_id)
                cursor.execute(
                    """UPDATE idempotency_record SET response_status=%s,response_body=%s::jsonb
                       WHERE tenant_id=%s AND service_name=%s AND idempotency_key=%s AND request_hash=%s""",
                    (status, payload, tenant_id, self.service_name, key, request_hash),
                )

    def abandon(self, tenant_id: str, key: str, request_hash: str):
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._tenant(cursor, tenant_id)
                cursor.execute(
                    """DELETE FROM idempotency_record
                       WHERE tenant_id=%s AND service_name=%s AND idempotency_key=%s
                         AND request_hash=%s AND response_status IS NULL""",
                    (tenant_id, self.service_name, key, request_hash),
                )


def durable_state_required() -> bool:
    default = "true" if os.getenv("ATLANTIS_ENV", "development") != "development" else "false"
    return os.getenv("ATLANTIS_REQUIRE_DURABLE_STATE", default).lower() == "true"


def build_nonce_store():
    dsn = postgres_dsn()
    ttl = int(os.getenv("ATLANTIS_WORKLOAD_NONCE_TTL_SECONDS", "120"))
    if dsn:
        return PostgresNonceStore.from_dsn(dsn, ttl)
    if durable_state_required():
        raise RuntimeError("POSTGRES_NONCE_STORE_REQUIRED")
    return MemoryNonceStore(ttl_seconds=ttl)


def build_idempotency_store(service_name: str):
    dsn = postgres_dsn()
    ttl = int(os.getenv("ATLANTIS_IDEMPOTENCY_TTL_SECONDS", "86400"))
    if dsn:
        return PostgresIdempotencyStore.from_dsn(dsn, service_name, ttl)
    if durable_state_required():
        raise RuntimeError("POSTGRES_IDEMPOTENCY_STORE_REQUIRED")
    return MemoryIdempotencyStore(service_name, ttl_seconds=ttl)
