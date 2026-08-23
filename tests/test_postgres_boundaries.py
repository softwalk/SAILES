import unittest
from types import SimpleNamespace

from _load import load

token_db = load("atlantis_token_db", "services/channel_adapters/app/postgres_token.py")


class FakeCursor:
    def __init__(self, returning=True): self.calls, self.returning = [], returning
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params): self.calls.append((" ".join(sql.split()), params))
    def fetchone(self): return ("id",) if self.returning else None


class FakeConnection:
    def __init__(self, cursor): self._cursor = cursor
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self._cursor


class PostgresBoundaryTests(unittest.TestCase):
    def test_atomic_token_consume_sets_tenant_and_conditions(self):
        cursor = FakeCursor()
        repository = token_db.PostgresTokenConsumer(lambda: FakeConnection(cursor))
        claims = SimpleNamespace(tenant_id="tenant-1")
        self.assertTrue(repository.consume("jti-1", claims))
        self.assertIn("set_config('app.tenant_id', %s, true)", cursor.calls[0][0])
        self.assertEqual(("tenant-1",), cursor.calls[0][1])
        update = cursor.calls[1][0]
        self.assertIn("consumed_at IS NULL", update)
        self.assertIn("revoked_at IS NULL", update)
        self.assertIn("expires_at > now()", update)


if __name__ == "__main__": unittest.main()
