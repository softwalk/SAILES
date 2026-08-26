#!/usr/bin/env python3
"""Validate ephemeral human tokens without calling or mutating an application API."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
from atlantis_contracts import HumanOIDCAuthenticator, RS256TokenVerifier  # noqa: E402


def load_keys(path: str) -> dict[str, bytes]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise RuntimeError("OIDC_PUBLIC_KEYS_INVALID")
    return {str(kid): str(pem).encode() for kid, pem in raw.items()}


def validate(args, token_file: str, scope: str, role: str, label: str):
    token = Path(token_file).read_text(encoding="utf-8").strip()
    if token.startswith("Bearer "):
        token = token[7:].strip()
    if not token:
        raise RuntimeError(f"{label.upper()}_TOKEN_MISSING")
    verifier = RS256TokenVerifier(args.issuer, args.audience, load_keys(args.public_keys))
    auth = HumanOIDCAuthenticator(verifier, scope, role)
    principal = auth.authenticate({"authorization": "Bearer " + token}, args.tenant)
    print(f"PASS OIDC {label} subject={principal.subject} tenant={principal.tenant_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--public-keys", required=True)
    parser.add_argument("--campaign-token", required=True)
    parser.add_argument("--reviewer-token", required=True)
    parser.add_argument("--campaign-role", default="CAMPAIGN_APPROVER")
    parser.add_argument("--reviewer-role", default="HUMAN_REVIEWER")
    args = parser.parse_args()
    validate(args, args.campaign_token, "campaign:approve", args.campaign_role, "campaign-approver")
    validate(args, args.reviewer_token, "human-action:decide", args.reviewer_role, "human-reviewer")


if __name__ == "__main__":
    main()
