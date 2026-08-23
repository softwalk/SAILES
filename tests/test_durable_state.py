import unittest

from _load import load
from atlantis_contracts.persistence import BoundedTTLMap, BoundedTTLSet, MemoryIdempotencyStore, MemoryNonceStore

crm_postgres = load("atlantis_crm_postgres_security", "services/crm_api/app/postgres.py")


class DurableStateTests(unittest.TestCase):
    def test_nonce_store_rejects_replay_and_expires(self):
        now = [100.0]
        store = MemoryNonceStore(ttl_seconds=10, clock=lambda: now[0])
        self.assertTrue(store.remember("policy", "n1", "t1", 100))
        self.assertFalse(store.remember("policy", "n1", "t1", 100))
        now[0] = 111.0
        self.assertTrue(store.remember("policy", "n1", "t1", 111))

    def test_idempotency_reservation_blocks_concurrency(self):
        store = MemoryIdempotencyStore("policy", clock=lambda: 100.0)
        self.assertEqual(("NEW", None), store.claim("t1", "k" * 16, "a" * 64))
        self.assertEqual(("PENDING", None), store.claim("t1", "k" * 16, "a" * 64))
        self.assertEqual(("CONFLICT", None), store.claim("t1", "k" * 16, "b" * 64))
        store.finish("t1", "k" * 16, "a" * 64, 201, {"ok": True})
        self.assertEqual(("CACHED", (201, {"ok": True})), store.claim("t1", "k" * 16, "a" * 64))

    def test_bounded_collections_evict_and_expire(self):
        now = [0.0]
        values = BoundedTTLMap(ttl_seconds=5, max_entries=2, clock=lambda: now[0])
        values["a"], values["b"], values["c"] = 1, 2, 3
        self.assertIsNone(values.get("a"))
        self.assertEqual(3, values["c"])
        seen = BoundedTTLSet(ttl_seconds=5, max_entries=2, clock=lambda: now[0])
        self.assertTrue(seen.remember("event"))
        self.assertFalse(seen.remember("event"))
        now[0] = 6.0
        self.assertTrue(seen.remember("event"))

    def test_global_suppression_requires_dedicated_admin_role(self):
        repository = crm_postgres.PostgresCRMRepository(lambda: None)
        with self.assertRaisesRegex(PermissionError, "GLOBAL_SUPPRESSION_REQUIRES_ADMIN_ROLE"):
            repository.suppress("tenant-1", {"scope": "GLOBAL", "phone_token": "token"})


if __name__ == "__main__":
    unittest.main()
