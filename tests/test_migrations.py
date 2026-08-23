import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MigrationContractTests(unittest.TestCase):
    def test_migrations_are_ordered_and_transactional(self):
        files = sorted((ROOT / "database").glob("*.sql"))
        self.assertEqual([p.name[:3] for p in files], ["001","002","003","004","005","006","007"])
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

    def test_005_has_cast_polcmd_text(self):
        """005 debe usar pol.polcmd::text (cast necesario para PostgreSQL real)."""
        text = (ROOT / "database/005_reconcile_migration_004_checksum.sql").read_text()
        self.assertIn("pol.polcmd::text", text, "005 debe usar pol.polcmd::text (cast)")

    def test_006_reconciles_005_without_touching_it(self):
        """006 reconcilia 005 sin modificar la fila 005 (registered + executed checksums)."""
        text = (ROOT / "database/006_reconcile_migration_005_applied_checksum.sql").read_text()
        self.assertIn("853d86220033dff82930c9e8e91589b6602eba6b00a43c795741a716143cf23e", text)
        self.assertIn("5ba50e9c2e465eea7e65a8c47f0ae89d2791e498ddd02c95c6dda04fa9e91d8d", text)
        self.assertNotIn("UPDATE schema_migration SET checksum", text)
        self.assertIn("prevent_migration_005_reconciliation_mutation", text)

    def test_006_is_immutable(self):
        """006 (aplicada) debe permanecer inmutable: el repo tiene el byte exacto de la aplicada."""
        import hashlib
        content = (ROOT / "database/006_reconcile_migration_005_applied_checksum.sql").read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        expected = "4f87541289fe1f105db6f63105e6674987cee7dedc3d3e96598f57b4953a9705"
        self.assertEqual(actual, expected,
            f"006 inmutable: el repo debe tener el byte exacto de la aplicada ({expected}), no {actual}")

    def test_006_runner_is_conditional_for_new_vs_existing(self):
        """El runner 22_apply_migration_006.sh es condicional: SKIP si 005=5ba50e9c (instalación nueva)."""
        text = (ROOT / "deploy/proxmox/operations/22_apply_migration_006.sh").read_text()
        self.assertIn("853d86220033dff82930c9e8e91589b6602eba6b00a43c795741a716143cf23e", text)
        self.assertIn("5ba50e9c2e465eea7e65a8c47f0ae89d2791e498ddd02c95c6dda04fa9e91d8d", text)
        self.assertIn("006 no aplica", text)

    def test_006_runner_uses_repo_dir_and_real_backup(self):
        """El runner 22_apply_migration_006.sh usa $REPO_DIR y backup PostgreSQL real."""
        text = (ROOT / "deploy/proxmox/operations/22_apply_migration_006.sh").read_text()
        self.assertIn("$REPO_DIR", text)
        self.assertNotIn("$ATLANTIS_REPO_ROOT", text)
        self.assertIn("pg_dump", text)
        self.assertIn("sha256sum -c", text)
        self.assertIn("fail \"pg_dump falló\"", text)

    def test_007_validates_canonical_fingerprint(self):
        """007 valida el fingerprint canónico de 005 contra el valor esperado (de47dcf7)."""
        text = (ROOT / "database/007_reconcile_migration_005_fingerprint_canonical.sql").read_text()
        self.assertIn("de47dcf79021fad19ba61aa308a372cb3a0d3da837c2b73191f4e7abd3934765", text)
        self.assertIn("migration_005_object_fingerprint_canonical", text)
        self.assertNotIn("UPDATE schema_migration SET checksum", text)


if __name__ == "__main__": unittest.main()
