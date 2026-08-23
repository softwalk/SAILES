#!/usr/bin/env python3
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/policy_gateway"))
sys.path.insert(0, str(ROOT / "shared"))

from atlantis_contracts import Channel, ContactabilityRequest, TokenVerifier, sha256_hex
from app.authorization import AuthorizationIssuer, InMemoryReplayLedger
from app.policy import PolicyEngine


def main():
    content_hash = sha256_hex({"message": "Demostración autorizada"})
    request = ContactabilityRequest(
        tenant_id="tenant-demo", contact_id="contact-demo", campaign_version_id="campaign-v1",
        purpose="PROMOTIONAL", channel=Channel.WHATSAPP, content_hash=content_hash,
        requested_at=datetime.now(UTC), campaign_approved=True, approved_content_hash=content_hash,
        consent_active=True, template_approved=True, conversation_window_open=False, local_hour=12,
    )
    decision = PolicyEngine().decide(request)
    ledger = InMemoryReplayLedger()
    secret = os.getenv("ATLANTIS_JIT_SECRET", "development-secret-change-me-000000").encode()
    token = AuthorizationIssuer(secret, ledger).issue(decision, request, "whatsapp-adapter", now=2_000_000_000)
    claims = TokenVerifier(secret, "atlantis-policy-gateway", ledger.consume).verify_and_consume(
        token, "whatsapp-adapter", {"tenant_id": "tenant-demo", "content_hash": content_hash}, now=2_000_000_001,
    )
    print({"decision": decision.outcome.value, "reasons": decision.reason_codes, "authorization_consumed": claims.jti})


if __name__ == "__main__": main()
