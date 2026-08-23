import unittest

from _load import load


crm = load("atlantis_crm_repep_campaign", "services/crm_api/app/domain.py")
evidence_module = load("atlantis_policy_evidence_campaign", "services/policy_gateway/app/evidence.py")


class FakeEvidenceService:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, path, body):
        self.calls.append((path, body))
        return dict(self.response)


class RepepCampaignConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.store = crm.CRMStore()
        self.contact = self.store.create_contact("t1", {"display_name": "Prospecto"})

    def evidence_for(self, campaign):
        self.store.approve_campaign("t1", campaign["id"], "legal-1", campaign["manifest_hash"])
        return self.store.contactability_evidence(
            "t1", self.contact["id"], "phone-token", "VOICE", "SALES", campaign["id"]
        )

    def test_campaign_repep_starts_disabled(self):
        campaign = self.store.create_campaign_version("t1", "campaign-1", {"content_hashes": {"voice": "a" * 64}})
        evidence = self.evidence_for(campaign)
        self.assertFalse(evidence["repep_enabled"])
        self.assertIsNone(evidence["repep_exemption_type"])
        self.assertFalse(evidence["repep_exemption_approved"])

    def test_approved_b2b_exception_is_returned_as_campaign_evidence(self):
        campaign = self.store.create_campaign_version("t1", "campaign-1", {
            "content_hashes": {"voice": "a" * 64},
            "repep": {
                "enabled": False,
                "exemption_type": "B2B",
                "exemption_approved": True,
                "exemption_evidence_ref": "legal/b2b/campaign-1.pdf",
            },
        })
        evidence = self.evidence_for(campaign)
        self.assertEqual(evidence["repep_exemption_type"], "B2B")
        self.assertTrue(evidence["repep_exemption_approved"])
        self.assertEqual(evidence["repep_exemption_evidence_ref"], "legal/b2b/campaign-1.pdf")

    def test_production_evidence_overrides_caller_repep_flags(self):
        service = FakeEvidenceService({
            "campaign_approved": True,
            "approved_content_hash": "a" * 64,
            "suppressed": False,
            "consent_active": False,
            "repep_snapshot_valid": False,
            "repep_listed": None,
            "repep_enabled": False,
            "repep_exemption_type": "B2B",
            "repep_exemption_approved": True,
            "repep_exemption_evidence_ref": "legal/b2b/approved.pdf",
        })
        body = {
            "tenant_id": "t1", "contact_id": "c1", "campaign_version_id": "v1",
            "channel": "VOICE", "purpose": "SALES",
            "repep_enabled": True,
            "repep_exemption_type": "B2C",
            "repep_exemption_approved": False,
        }
        resolved = evidence_module.EvidenceClient(service).resolve(body)
        self.assertFalse(resolved["repep_enabled"])
        self.assertEqual(resolved["repep_exemption_type"], "B2B")
        self.assertTrue(resolved["repep_exemption_approved"])


if __name__ == "__main__":
    unittest.main()
