import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MigrationContractTests(unittest.TestCase):
    def test_migrations_are_ordered_and_transactional(self):
        files = sorted((ROOT / "database").glob("*.sql"))
        self.assertEqual([p.name[:3] for p in files], ["001","002","003","004","005","006"])
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
        # Registra ambos checksums (registered 853d8622 + executed 5ba50e9c)
        self.assertIn("853d86220033dff82930c9e8e91589b6602eba6b00a43c795741a716143cf23e", text)
        self.assertIn("5ba50e9c2e465eea7e65a8c47f0ae89d2791e498ddd02c95c6dda04fa9e91d8d", text)
        # NO modifica la fila 005 (sin UPDATE schema_migration SET checksum)
        self.assertNotIn("UPDATE schema_migration SET checksum", text)
        # Append-only (trigger)
        self.assertIn("prevent_migration_005_reconciliation_mutation", text)

    def test_006_is_conditional_for_new_vs_existing(self):
        """006 es condicional: SKIP si 005=5ba50e9c (instalación nueva), aplica si 005=853d8622."""
        text = (ROOT / "database/006_reconcile_migration_005_applied_checksum.sql").read_text()
        # Detecta el estado de 005 (registrada como 853d8622 o 5ba50e9c)
        self.assertIn("853d86220033dff82930c9e8e91589b6602eba6b00a43c795741a716143cf23e", text)
        self.assertIn("5ba50e9c2e465eea7e65a8c47f0ae89d2791e498ddd02c95c6dda04fa9e91d8d", text)
        # Es condicional (instalación nueva no aplica)
        self.assertIn("instalación nueva", text)

    def test_006_runner_uses_repo_dir_and_real_backup(self):
        """El runner 22_apply_migration_006.sh usa $REPO_DIR y backup PostgreSQL real."""
        text = (ROOT / "deploy/proxmox/operations/22_apply_migration_006.sh").read_text()
        # Usa $REPO_DIR (no $ATLANTIS_REPO_ROOT)
        self.assertIn("$REPO_DIR", text)
        self.assertNotIn("$ATLANTIS_REPO_ROOT", text)
        # Backup PostgreSQL real (pg_dump + checksum + verificación)
        self.assertIn("pg_dump", text)
        self.assertIn("sha256sum -c", text)
        # Aborta si el backup falla
        self.assertIn("fail \"pg_dump falló\"", text)


if __name__ == "__main__": unittest.main()
