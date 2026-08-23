import subprocess
import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "deploy" / "proxmox" / "operations"


class OperationsKitTests(unittest.TestCase):
    def test_all_shell_scripts_are_syntactically_valid(self):
        scripts = sorted(OPS.glob("*.sh")) + [ROOT / "deploy/proxmox/validate_infrastructure.sh"]
        self.assertGreaterEqual(len(scripts), 11)
        for script in scripts:
            result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"{script}: {result.stderr}")

    def test_mutating_scripts_require_explicit_execute(self):
        for name in (
            "01_prepare_secret_permissions.sh", "10_backup.sh", "20_apply_migration_004.sh",
            "21_apply_migration_005.sh", "30_build_images.sh", "40_deploy_shadow.sh", "60_rollback.sh",
        ):
            result = subprocess.run([str(OPS / name)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, name)
            self.assertIn("--execute", result.stderr + result.stdout)

    def test_compose_has_rc4_images_and_no_shared_secret_group(self):
        compose = (ROOT / "deploy/proxmox/compose.application.yaml").read_text()
        self.assertNotIn("group_add:", compose)
        for service in (
            "policy-gateway", "crm-api", "orchestrator", "model-gateway",
            "voice-adapter", "whatsapp-adapter", "marketia-adapter",
        ):
            self.assertIn(f"image: atlantis-{service}:${{ATLANTIS_RELEASE_TAG:-0.9.0-rc4}}", compose)

    def test_rollout_keeps_shadow_and_backup_gates(self):
        preflight = (OPS / "00_preflight.sh").read_text()
        migration = (OPS / "20_apply_migration_004.sh").read_text()
        rollback = (OPS / "60_rollback.sh").read_text()
        self.assertIn("ATLANTIS_SHADOW_MODE", preflight)
        self.assertIn('require_file "$backup_dir/atlantis.dump"', migration)
        self.assertIn("security-critical", rollback)

    def test_migration_005_preserves_history_and_requires_approval(self):
        migration = (ROOT / "database/005_reconcile_migration_004_checksum.sql").read_text()
        self.assertNotIn("UPDATE schema_migration SET", migration)
        self.assertIn("schema_migration_reconciliation is append-only", migration)
        self.assertIn("approved_by text NOT NULL", migration)
        self.assertIn("approved_date date NOT NULL", migration)
        self.assertIn("evidence_sha256 text NOT NULL", migration)
        for attribute in ("rolsuper", "rolinherit", "rolcreaterole", "rolcreatedb", "rolcanlogin", "rolbypassrls"):
            self.assertIn(attribute, migration)
        self.assertIn("53e77f497b6ee0e30963dd08a734dd7b2d1a997c52c742ee42bb4c6228818b6d", migration)

    def test_corrected_role_fingerprint_has_six_attributes(self):
        canonical = """FUNC:ab92646ad643360c80f948ff3dee7a26
GRANT:DELETE
GRANT:INSERT
GRANT:SELECT
GRANT:UPDATE
POLICY:suppression_global_admin:((scope = 'GLOBAL'::text) AND (tenant_id IS NULL)):((scope = 'GLOBAL'::text) AND (tenant_id IS NULL) AND (contact_id IS NULL) AND (phone_token IS NOT NULL)):*
POLICY:suppression_tenant_and_global_read:((tenant_id = app.current_tenant_id()) OR ((scope = 'GLOBAL'::text) AND (tenant_id IS NULL)))::r
POLICY:suppression_tenant_delete:((tenant_id = app.current_tenant_id()) AND (scope <> 'GLOBAL'::text))::d
POLICY:suppression_tenant_insert::((tenant_id = app.current_tenant_id()) AND (scope <> 'GLOBAL'::text)):a
POLICY:suppression_tenant_update:((tenant_id = app.current_tenant_id()) AND (scope <> 'GLOBAL'::text)):((tenant_id = app.current_tenant_id()) AND (scope <> 'GLOBAL'::text)):w
ROLE:atlantis_suppression_admin:falsefalsefalsefalsefalsefalse
"""
        self.assertEqual(hashlib.sha256(canonical.encode()).hexdigest(),
                         "53e77f497b6ee0e30963dd08a734dd7b2d1a997c52c742ee42bb4c6228818b6d")

    def test_pilot_gate_checks_real_runtime_conditions(self):
        gate = (OPS / "00_preflight_pilot_gate.sh").read_text()
        self.assertIn('[[ "$environment" == "production" ]]', gate)
        self.assertIn("pg_stat_ssl", gate)
        self.assertIn("database_runtime_psql", gate)
        self.assertNotIn("docker exec", gate)
        self.assertIn("migration_004_object_fingerprint", gate)
        self.assertIn("approved_date", gate)
        self.assertIn("evidence_sha256", gate)
        self.assertIn("ATLANTIS_MIN_AVAILABLE_MEMORY_KIB", gate)
        self.assertIn("git -C", gate)
        self.assertIn("configured_providers", gate)


if __name__ == "__main__":
    unittest.main()
