#!/usr/bin/env python3
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


crm = load("e2e_crm", "services/crm_api/app/domain.py")
workflow = load("e2e_workflow", "services/orchestrator/app/workflow.py")
policy = load("e2e_policy", "services/policy_gateway/app/policy.py")
authorization = load("e2e_authorization", "services/policy_gateway/app/authorization.py")
whatsapp = load("e2e_whatsapp", "services/channel_adapters/app/whatsapp.py")

from atlantis_contracts import Channel, ContactabilityRequest, TokenVerifier, sha256_hex


class NeverSendTransport:
    def send(self, command, token):
        raise AssertionError("SHADOW_MODE_MUST_NOT_CALL_PROVIDER")


def main():
    store = crm.CRMStore()
    contact = store.create_contact("tenant-1", {"display_name": "Prospecto de prueba"})
    campaign = store.create_campaign_version("tenant-1", "campaign-1", {"message": "Hola", "channel": "WHATSAPP"})
    store.approve_campaign("tenant-1", campaign["id"], "human-1", campaign["manifest_hash"])
    store.grant_consent("tenant-1", contact["id"], "WHATSAPP", sha256_hex({"evidence": "test"}))

    graph = workflow.WorkflowEngine()
    state = graph.start("tenant-1", campaign["id"], contact["id"])
    state = graph.transition(state, "evt-qualify")
    state = graph.transition(state, "evt-prepare")
    state = graph.transition(state, "evt-approval-request", {"subject_hash": campaign["manifest_hash"]})
    state = graph.decide_human_action(state, state.pending_human_action_id, True, "human-1", campaign["manifest_hash"])

    content_hash = sha256_hex({"message": "Hola"})
    intent = ContactabilityRequest(
        tenant_id="tenant-1", contact_id=contact["id"], campaign_version_id=campaign["id"],
        purpose="PROMOTIONAL", channel=Channel.WHATSAPP, content_hash=content_hash,
        requested_at=datetime.now(UTC), campaign_approved=True, approved_content_hash=content_hash,
        consent_active=True, template_approved=True, conversation_window_open=False, local_hour=12,
    )
    decision = policy.PolicyEngine().decide(intent)
    ledger, secret = authorization.InMemoryReplayLedger(), b"s" * 32
    token = authorization.AuthorizationIssuer(secret, ledger).issue(decision, intent, "whatsapp-adapter")
    adapter = whatsapp.WhatsAppAdapter(TokenVerifier(secret, "atlantis-policy-gateway", ledger.consume), NeverSendTransport(), shadow_mode=True)
    receipt = adapter.send(token, {"tenant_id": "tenant-1", "contact_id": contact["id"],
                    "campaign_version_id": campaign["id"], "content_hash": content_hash})
    effect = graph.enqueue_effect(state, {"channel": "WHATSAPP", "receipt": receipt}, "dispatch-1")
    print({"run_id": state.run_id, "decision": decision.outcome.value, "dispatch": receipt["status"], "outbox": effect["status"], "audit_events": len(store.audit)})


if __name__ == "__main__": main()
