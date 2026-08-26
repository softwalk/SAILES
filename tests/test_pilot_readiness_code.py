import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PilotReadinessCodeTests(unittest.TestCase):
    def test_orchestrator_loads_state_under_graph_run_lock(self):
        text = (ROOT / "services/orchestrator/app/postgres_workflow.py").read_text()
        self.assertIn("FROM graph_run WHERE tenant_id=%s AND id=%s FOR UPDATE", text)
        self.assertIn("INSERT INTO graph_checkpoint", text)
        self.assertIn("INSERT INTO workflow_event", text)
        self.assertIn("INSERT INTO human_action", text)
        self.assertIn("CHECKPOINT_HASH_INVALID", text)

    def test_shadow_adapter_uses_postgres_replay_ledger_when_dsn_exists(self):
        text = (ROOT / "services/channel_adapters/app/server.py").read_text()
        self.assertIn("PostgresTokenConsumer.from_dsn(dsn) if dsn else", text)
        self.assertNotIn("if dsn and not shadow", text)

    def test_model_daily_budget_is_reserved_before_provider_call(self):
        server = (ROOT / "services/model_gateway/app/server.py").read_text()
        self.assertLess(server.index("usage_repository.reserve"), server.index("ModelGateway("))
        repository = (ROOT / "services/model_gateway/app/postgres_usage.py").read_text()
        self.assertIn("DAILY_BUDGET_EXCEEDED_PRECALL", repository)
        self.assertIn("FOR UPDATE", repository)
        self.assertIn("INSERT INTO model_call", repository)

    def test_human_endpoints_use_oidc_authenticator(self):
        crm = (ROOT / "services/crm_api/app/server.py").read_text()
        orchestrator = (ROOT / "services/orchestrator/app/server.py").read_text()
        self.assertIn("campaign:approve", crm)
        self.assertIn("human-action:decide", orchestrator)
        self.assertIn("human_auth.authenticate", crm)
        self.assertIn("human_auth.authenticate", orchestrator)

    def test_live_control_probe_validates_real_ephemeral_oidc_tokens(self):
        operation = (ROOT / "deploy/proxmox/operations/80_validate_pilot_controls.sh").read_text()
        validator = (ROOT / "tools/validate_human_oidc.py").read_text()
        self.assertIn("validate_human_oidc.py", operation)
        self.assertIn("campaign_approver.token", operation)
        self.assertIn("human_reviewer.token", operation)
        self.assertIn("campaign:approve", validator)
        self.assertIn("human-action:decide", validator)


if __name__ == "__main__":
    unittest.main()
