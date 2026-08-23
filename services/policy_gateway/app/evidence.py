class EvidenceClient:
    def __init__(self, client): self.client = client

    def resolve(self, request_body: dict) -> dict:
        required = {key:request_body[key] for key in ("tenant_id","contact_id","campaign_version_id","channel","purpose")}
        required["phone_token"] = request_body.get("phone_token")
        evidence = self.client.post("/v1/contactability-evidence", required)
        return {**request_body,
                "campaign_approved":evidence.get("campaign_approved",False),
                "approved_content_hash":evidence.get("approved_content_hash"),
                "internally_suppressed":evidence.get("suppressed",True),
                "consent_active":evidence.get("consent_active",False),
                "repep_snapshot_valid":evidence.get("repep_snapshot_valid",False),
                "repep_listed":evidence.get("repep_listed")}
