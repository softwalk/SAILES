import base64
import json
import time
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from _load import load
from atlantis_contracts import RS256TokenVerifier, WorkloadRequestVerifier, normalize_e164, phone_token
from atlantis_contracts.security import sign_workload_request

leads = load("atlantis_leads", "services/agent_adapters/app/lead_intelligence.py")
repep = load("atlantis_repep", "services/policy_gateway/app/repep.py")
sensitivity = load("atlantis_sensitivity", "services/policy_gateway/app/sensitivity.py")


def b64(value: bytes): return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


class SecurityGovernanceTests(unittest.TestCase):
    def test_mexican_phone_normalization_and_token(self):
        self.assertEqual(normalize_e164("55 1234 5678"), "+525512345678")
        self.assertEqual(phone_token("+52 55 1234 5678", b"p" * 32), phone_token("5512345678", b"p" * 32))

    def test_workload_signature_and_replay(self):
        seen = set()
        remember = lambda service, nonce, tenant, issued: False if (tenant, service, nonce) in seen else not seen.add((tenant, service, nonce))
        verifier = WorkloadRequestVerifier({"orchestrator": b"k" * 32}, remember)
        signature = sign_workload_request(b"k" * 32, 1000, "n-1", "POST", "/v1/x", b"{}")
        self.assertEqual(verifier.verify("orchestrator", "1000", "n-1", signature, "POST", "/v1/x", b"{}", "t1", now=1001), "orchestrator")
        with self.assertRaisesRegex(PermissionError, "REPLAY"):
            verifier.verify("orchestrator", "1000", "n-1", signature, "POST", "/v1/x", b"{}", "t1", now=1001)

    def test_oidc_rs256_verification(self):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        header = b64(json.dumps({"alg":"RS256","typ":"JWT","kid":"k1"}, separators=(",",":")).encode())
        payload = b64(json.dumps({"iss":"https://id.example","aud":"atlantis","sub":"u1","tenant_id":"t1",
                                  "scope":"campaign:approve","roles":["APPROVER"],"exp":2000,"nbf":900}, separators=(",",":")).encode())
        signature = b64(key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256()))
        principal = RS256TokenVerifier("https://id.example", "atlantis", {"k1": public}).verify(f"{header}.{payload}.{signature}", now=1000)
        principal.require("campaign:approve", role="APPROVER")
        self.assertEqual(principal.tenant_id, "t1")

    def test_repep_snapshot_hash_and_lookup(self):
        raw = b"token-a\ntoken-b\n"
        from atlantis_contracts import sha256_hex
        snapshot = repep.RepepSnapshot("dataset-1", "t1", datetime.now(UTC)-timedelta(days=1),
                                       datetime.now(UTC)+timedelta(days=1), "receipt-1", "s3://evidence", sha256_hex(raw), frozenset({"token-a"}))
        registry = repep.RepepRegistry()
        registry.import_snapshot(snapshot, raw)
        self.assertTrue(registry.check("t1", "dataset-1", "token-a")["listed"])
        self.assertFalse(registry.check("t1", "dataset-1", "token-c")["listed"])

    def test_lead_governance_scoring_and_dedup(self):
        lead = leads.Lead("Acme", None, "https://acme.example", "p1", "https://source.example/1", "CC-BY-4.0",
                          datetime.now(UTC), .9, {"industry":"BPO","employees":200,"region":"MX"})
        leads.LeadGovernance({"source.example"}, {"CC-BY-4.0"}).validate(lead)
        score = leads.LeadScorer().score(lead, {"industries":["BPO"],"min_employees":100,"max_employees":500,"regions":["MX"]})
        self.assertGreaterEqual(score["score"], 90)
        self.assertEqual(leads.LeadDeduplicator().classify(lead, lead), "MATCH")

    def test_sensitive_opportunity_requires_human(self):
        action = sensitivity.OpportunityAction("OFFER", amount=Decimal("50000"), discount_percent=Decimal("10"))
        result, reasons = sensitivity.SensitivityPolicy().evaluate(action)
        self.assertEqual(result, "HUMAN_REVIEW")
        self.assertIn("DISCOUNT_REQUIRES_HUMAN", reasons)


if __name__ == "__main__": unittest.main()
