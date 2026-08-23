class MarketiaAdapter:
    """Anti-corruption layer; Marketia never owns compliance fields."""

    protected_fields = {
        "consent", "consent_active", "suppression", "suppressed", "contactable",
        "policy_decision", "repep_status", "campaign_approved", "outbound_authorization",
    }
    allowed_fields = {"marketia_ref", "utm_source", "utm_campaign", "attribution", "creative_ref", "engagement_score"}

    def ingest(self, payload: dict, contract_version: str) -> dict:
        if contract_version != "marketia@1":
            raise ValueError("UNSUPPORTED_MARKETIA_CONTRACT")
        if self.protected_fields.intersection(payload):
            raise PermissionError("MARKETIA_CANNOT_OVERRIDE_COMPLIANCE")
        unknown = set(payload) - self.allowed_fields
        if unknown:
            raise ValueError("UNKNOWN_MARKETIA_FIELDS:" + ",".join(sorted(unknown)))
        return dict(payload)


class MarketiaTransport:
    def __init__(self, http, base_url: str, api_token: str):
        if not base_url or not api_token: raise RuntimeError("MARKETIA_NOT_CONFIGURED")
        self.http, self.base_url, self.api_token = http, base_url.rstrip("/"), api_token

    def push(self, entity_type: str, entity_id: str, version: str, payload: dict) -> dict:
        clean = MarketiaAdapter().ingest(payload, "marketia@1")
        return self.http.post_json(f"{self.base_url}/v1/sync/{entity_type}/{entity_id}",
                                   {"version": version, "payload": clean}, {"Authorization": f"Bearer {self.api_token}"})
