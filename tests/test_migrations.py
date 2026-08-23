import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MigrationContractTests(unittest.TestCase):
    def test_migrations_are_ordered_and_transactional(self):
        files = sorted((ROOT / "database").glob("*.sql"))
        self.assertEqual([p.name[:3] for p in files], ["001","002","003","004","005"])
        for path in files[1:]:
            text = path.read_text().strip()
            self.assertTrue(text.startswith("--"))
            self.assertIn("BEGIN;", text)
            self.assertRegex(text, r"COMMIT;\s*(?:--[^\n]*\s*)*$")

    def test_runtime_tables_have_forced_rls(self):
        text = (ROOT / "database/003_runtime_controls.sql").read_text()
        self.assertIn("FORCE ROW LEVEL SECURITY", text)
        for table in ("idempotency_record","workload_nonce","frequency_counter"):
            self.assertIn(table, text)

    def test_audit_function_is_serialized_and_not_public(self):
        text = (ROOT / "database/003_runtime_controls.sql").read_text()
        self.assertIn("FOR UPDATE", text)
        self.assertIn("REVOKE ALL ON FUNCTION app.append_audit_event", text)

    def test_global_suppression_has_separate_read_and_admin_write_policies(self):
        text = (ROOT / "database/004_security_and_durability.sql").read_text()
        self.assertIn("scope = 'GLOBAL' AND tenant_id IS NULL", text)
        self.assertIn("suppression_tenant_and_global_read", text)
        self.assertIn("suppression_global_admin", text)
        self.assertIn("TO atlantis_suppression_admin", text)


if __name__ == "__main__": unittest.main()
