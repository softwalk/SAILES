import unittest
from datetime import UTC, datetime, timedelta

from _load import load
from atlantis_contracts import Channel, ContactabilityRequest, DecisionOutcome, TokenError, TokenVerifier, sha256_hex

policy_mod = load("atlantis_policy", "services/policy_gateway/app/policy.py")
auth_mod = load("atlantis_auth", "services/policy_gateway/app/authorization.py")


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.content_hash = sha256_hex({"message": "hola"})
        self.base = dict(
            tenant_id="t1", contact_id="c1", campaign_version_id="v1", purpose="PROMOTIONAL",
            channel=Channel.VOICE, content_hash=self.content_hash, requested_at=datetime.now(UTC),
            campaign_approved=True, approved_content_hash=self.content_hash, local_hour=12,
            repep_enabled=True, repep_snapshot_valid=True, repep_listed=False,
        )

    def test_voice_allowed_with_current_repep(self):
        decision = policy_mod.PolicyEngine().decide(ContactabilityRequest(**self.base))
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOW)

    def test_voice_fails_closed_without_repep(self):
        request = ContactabilityRequest(**{**self.base, "repep_snapshot_valid": None})
        decision = policy_mod.PolicyEngine().decide(request)
        self.assertEqual(decision.outcome, DecisionOutcome.DENY)
        self.assertIn("REPEP_EVIDENCE_MISSING_OR_STALE", decision.reason_codes)

    def test_repep_starts_disabled_but_requires_approved_b2b_exception(self):
        request = ContactabilityRequest(**{
            **self.base,
            "repep_enabled": False,
            "repep_snapshot_valid": None,
            "repep_listed": None,
        })
        decision = policy_mod.PolicyEngine().decide(request)
        self.assertEqual(decision.outcome, DecisionOutcome.DENY)
        self.assertIn("REPEP_DISABLED_REQUIRES_B2B", decision.reason_codes)
        self.assertIn("REPEP_B2B_EXCEPTION_NOT_APPROVED", decision.reason_codes)
        self.assertIn("REPEP_B2B_EVIDENCE_MISSING", decision.reason_codes)

    def test_approved_b2b_campaign_can_disable_repep(self):
        request = ContactabilityRequest(**{
            **self.base,
            "repep_enabled": False,
            "repep_snapshot_valid": None,
            "repep_listed": None,
            "repep_exemption_type": "B2B",
            "repep_exemption_approved": True,
            "repep_exemption_evidence_ref": "legal/b2b/campaign-v1.pdf",
        })
        decision = policy_mod.PolicyEngine().decide(request)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOW)
        self.assertEqual(decision.policy_version, "mx-contactability@2")

    def test_b2c_campaign_cannot_bypass_repep(self):
        request = ContactabilityRequest(**{
            **self.base,
            "repep_enabled": False,
            "repep_exemption_type": "B2C",
            "repep_exemption_approved": True,
            "repep_exemption_evidence_ref": "legal/review.pdf",
        })
        decision = policy_mod.PolicyEngine().decide(request)
        self.assertEqual(decision.outcome, DecisionOutcome.DENY)
        self.assertIn("REPEP_DISABLED_REQUIRES_B2B", decision.reason_codes)

    def test_whatsapp_requires_opt_in_and_template(self):
        request = ContactabilityRequest(**{**self.base, "channel": Channel.WHATSAPP, "consent_active": False})
        decision = policy_mod.PolicyEngine().decide(request)
        self.assertIn("WHATSAPP_OPT_IN_MISSING", decision.reason_codes)
        self.assertIn("WHATSAPP_TEMPLATE_OR_WINDOW_INVALID", decision.reason_codes)

    def test_campaign_change_invalidates_contact(self):
        request = ContactabilityRequest(**{**self.base, "approved_content_hash": "0" * 64})
        self.assertIn("CAMPAIGN_CONTENT_CHANGED", policy_mod.PolicyEngine().decide(request).reason_codes)

    def test_token_is_single_use(self):
        request = ContactabilityRequest(**self.base)
        decision = policy_mod.PolicyEngine().decide(request)
        ledger = auth_mod.InMemoryReplayLedger()
        secret = b"x" * 32
        now = int(decision.decided_at.timestamp())
        token = auth_mod.AuthorizationIssuer(secret, ledger).issue(decision, request, "voice-adapter", now=now)
        verifier = TokenVerifier(secret, "atlantis-policy-gateway", ledger.consume)
        expected = {"tenant_id": "t1", "content_hash": self.content_hash}
        verifier.verify_and_consume(token, "voice-adapter", expected, now=now + 1)
        with self.assertRaisesRegex(TokenError, "TOKEN_REPLAY"):
            verifier.verify_and_consume(token, "voice-adapter", expected, now=now + 1)

    def test_stale_decision_cannot_issue_token(self):
        request = ContactabilityRequest(**self.base)
        decision = policy_mod.PolicyEngine().decide(request)
        stale_now = int((decision.decided_at + timedelta(seconds=121)).timestamp())
        with self.assertRaisesRegex(PermissionError, "DECISION_EXPIRED"):
            auth_mod.AuthorizationIssuer(b"x" * 32, auth_mod.InMemoryReplayLedger()).issue(
                decision, request, "voice-adapter", now=stale_now,
            )

    def test_decision_context_is_tenant_bound_and_one_shot(self):
        request = ContactabilityRequest(**self.base)
        decision = policy_mod.PolicyEngine().decide(request)
        contexts = auth_mod.DecisionContextStore(clock=lambda: 1000)
        contexts.put(decision, request)
        with self.assertRaisesRegex(PermissionError, "TENANT_MISMATCH"):
            contexts.take(decision.decision_id, "other")
        self.assertIsNotNone(contexts.take(decision.decision_id, "t1"))
        self.assertIsNone(contexts.take(decision.decision_id, "t1"))

    def test_denied_decision_cannot_issue_token(self):
        request = ContactabilityRequest(**{**self.base, "kill_switch": True})
        decision = policy_mod.PolicyEngine().decide(request)
        with self.assertRaises(PermissionError):
            auth_mod.AuthorizationIssuer(b"x" * 32, auth_mod.InMemoryReplayLedger()).issue(decision, request, "voice-adapter")


if __name__ == "__main__": unittest.main()
