import unittest

from _load import load
from atlantis_contracts import sha256_hex

crm = load("atlantis_crm", "services/crm_api/app/domain.py")
workflow = load("atlantis_workflow", "services/orchestrator/app/workflow.py")
marketia = load("atlantis_marketia", "services/channel_adapters/app/marketia.py")
salesgpt = load("atlantis_salesgpt", "services/agent_adapters/app/salesgpt.py")


class DomainTests(unittest.TestCase):
    def test_campaign_approval_is_bound_to_hash(self):
        store = crm.CRMStore()
        row = store.create_campaign_version("t1", "campaign", {"message": "a"})
        store.approve_campaign("t1", row["id"], "human-1", row["manifest_hash"])
        changed = store.amend_campaign("t1", row["id"], {"message": "b"})
        self.assertEqual(changed["status"], "PENDING_APPROVAL")
        self.assertIsNone(changed["approved_hash"])

    def test_audit_chain_is_linked(self):
        store = crm.CRMStore()
        contact = store.create_contact("t1", {"name": "Lead"})
        store.suppress("t1", contact["id"])
        self.assertEqual(store.audit[1]["previous_hash"], store.audit[0]["event_hash"])

    def test_audit_chain_is_isolated_by_tenant(self):
        store = crm.CRMStore()
        store.create_contact("t1", {"name": "A"})
        store.create_contact("t2", {"name": "B"})
        self.assertIsNone(store.audit[1]["previous_hash"])
        self.assertEqual(store.audit[1]["sequence_no"], 1)

    def test_orchestrator_event_and_effect_are_idempotent(self):
        engine = workflow.WorkflowEngine()
        state = engine.start("t1", "v1", "c1")
        advanced = engine.transition(state, "evt-1")
        same = engine.transition(advanced, "evt-1")
        self.assertEqual(same, advanced)
        a = engine.enqueue_effect(advanced, {"kind": "contact"}, "key-1")
        b = engine.enqueue_effect(advanced, {"kind": "contact"}, "key-1")
        self.assertEqual(a["id"], b["id"])

    def test_human_approval_checks_subject_hash(self):
        engine = workflow.WorkflowEngine()
        state = engine.start("t1", "v1", "c1")
        state = engine.transition(state, "1")
        state = engine.transition(state, "2")
        waiting = engine.transition(state, "3", {"subject_hash": sha256_hex({"campaign": 1})})
        with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
            engine.decide_human_action(waiting, waiting.pending_human_action_id, True, "human", "wrong")

    def test_marketia_cannot_enable_contact(self):
        with self.assertRaises(PermissionError):
            marketia.MarketiaAdapter().ingest({"contactable": True}, "marketia@1")

    def test_salesgpt_cannot_send(self):
        result = salesgpt.SalesGPTPolicy().evaluate({"action": "send_message", "text": "hola"})
        self.assertEqual(result["status"], "DENIED")


if __name__ == "__main__": unittest.main()
