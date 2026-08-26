import unittest
from types import SimpleNamespace
from unittest.mock import patch

from _load import load

crm_postgres = load("atlantis_crm_campaign_postgres", "services/crm_api/app/postgres.py")


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []
        self.description = []

    def __enter__(self): return self
    def __exit__(self, *_): return False

    def execute(self, sql, params):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, params))
        if "RETURNING id,tenant_id,campaign_id" in normalized:
            self.description = [SimpleNamespace(name=name) for name in (
                "id", "tenant_id", "campaign_id", "version_no", "status",
                "purpose", "manifest_hash", "created_by",
            )]

    def fetchone(self):
        return self.rows.pop(0)


class FakeConnection:
    def __init__(self, cursor): self._cursor = cursor
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def cursor(self): return self._cursor


class CampaignPostgresTests(unittest.TestCase):
    def test_create_campaign_persists_version_and_canonical_artifact(self):
        returned = ("version-1", "tenant-1", "campaign-1", 1, "PENDING_APPROVAL",
                    "PROMOTIONAL", "a" * 64, "user-1")
        cursor = FakeCursor([("campaign-1",), (1,), returned])
        repository = crm_postgres.PostgresCRMRepository(lambda: FakeConnection(cursor))
        manifest = {"name": "Synthetic", "purpose": "PROMOTIONAL", "created_by": "user-1"}
        with patch.object(crm_postgres, "uuid4", side_effect=["version-1", "owner-1", "artifact-1"]):
            result = repository.create_campaign_version("tenant-1", "campaign-1", manifest)
        statements = "\n".join(sql for sql, _ in cursor.calls)
        self.assertEqual(result["status"], "PENDING_APPROVAL")
        self.assertIn("INSERT INTO campaign_version", statements)
        self.assertIn("INSERT INTO campaign_artifact", statements)
        self.assertIn("FOR UPDATE", statements)

    def test_approval_is_hash_bound_and_updates_campaign_status(self):
        digest = "b" * 64
        returned = ("version-1", "tenant-1", "campaign-1", 1, "APPROVED",
                    "PROMOTIONAL", digest, "user-1")
        cursor = FakeCursor([(digest,), returned])
        repository = crm_postgres.PostgresCRMRepository(lambda: FakeConnection(cursor))
        with patch.object(crm_postgres, "uuid4", return_value="approval-1"):
            result = repository.approve_campaign(
                "tenant-1", "version-1", "approver-1", digest, "CAMPAIGN_APPROVER", "shadow test",
            )
        statements = "\n".join(sql for sql, _ in cursor.calls)
        self.assertEqual(result["status"], "APPROVED")
        self.assertIn("INSERT INTO approval", statements)
        self.assertIn("artifact_hash=%s", statements)

    def test_approval_rejects_changed_manifest_hash_before_write(self):
        cursor = FakeCursor([("a" * 64,)])
        repository = crm_postgres.PostgresCRMRepository(lambda: FakeConnection(cursor))
        with self.assertRaisesRegex(ValueError, "APPROVAL_HASH_MISMATCH"):
            repository.approve_campaign("tenant-1", "version-1", "approver-1", "b" * 64)
        self.assertEqual(len(cursor.calls), 2)  # tenant context + locked hash read only


if __name__ == "__main__":
    unittest.main()
