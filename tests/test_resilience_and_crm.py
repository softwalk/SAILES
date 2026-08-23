import unittest
from datetime import UTC, datetime, timedelta

from _load import load

resilience = load("atlantis_resilience", "services/orchestrator/app/resilience.py")
workflow = load("atlantis_workflow_resilience", "services/orchestrator/app/workflow.py")
crm = load("atlantis_crm_extended", "services/crm_api/app/domain.py")


class ResilienceCRMTests(unittest.TestCase):
    def test_policy_denial_is_never_retried(self):
        worker = resilience.OutboxWorker(lambda item: (_ for _ in ()).throw(resilience.PolicyDenial("DENIED")), lambda a,b: None)
        result = worker.process({"status":"PENDING","attempts":0})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn("retry_after_seconds", result)

    def test_transient_failure_retries_then_dead_letters(self):
        worker = resilience.OutboxWorker(lambda item: "auth", lambda item, auth: (_ for _ in ()).throw(resilience.TransientFailure("DOWN")),
                                         resilience.RetryPolicy(max_attempts=2))
        first = worker.process({"status":"PENDING","attempts":0})
        second = worker.process(first)
        self.assertEqual(first["status"], "RETRY")
        self.assertEqual(second["status"], "DEAD")

    def test_circuit_breaker_opens_and_recovers(self):
        now = [0]
        breaker = resilience.CircuitBreaker(2, 10, lambda: now[0])
        breaker.failure(); breaker.failure()
        self.assertFalse(breaker.allow())
        now[0] = 11
        self.assertTrue(breaker.allow())

    def test_expired_human_action_blocks_run(self):
        engine = workflow.WorkflowEngine()
        state = engine.start("t1","v1","c1")
        state = engine.transition(state,"1"); state = engine.transition(state,"2")
        state = engine.transition(state,"3",{"subject_hash":"h"})
        engine.human_actions[state.pending_human_action_id]["expires_at"] = (datetime.now(UTC)-timedelta(seconds=1)).isoformat()
        states = {state.run_id: state}
        changed = engine.expire_human_actions(states)
        self.assertEqual(changed[0].status, "BLOCKED")

    def test_crm_extended_entities_and_tenant_export(self):
        store = crm.CRMStore()
        contact = store.create_contact("t1", {"display_name":"A"})
        store.record_interaction("t1", contact["id"], {"provider":"meta","provider_ref":"m1","channel":"WHATSAPP"})
        store.upsert_opportunity("t1", contact["id"], {"stage":"QUALIFIED"})
        store.add_memory_fact("t1", contact["id"], {"predicate":"interest","value":{"product":"x"},"fact_kind":"DECLARED","confidence":1})
        store.request_arco("t1", contact["id"], "ACCESS", "verified-1")
        export = store.export_contact("t1", contact["id"])
        self.assertEqual(len(export["interactions"]), 1)
        self.assertEqual(len(export["opportunities"]), 1)
        self.assertEqual(len(export["memory_facts"]), 1)


if __name__ == "__main__": unittest.main()
