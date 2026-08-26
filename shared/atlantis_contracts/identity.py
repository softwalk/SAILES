"""Human identity verification for approval endpoints.

Workload HMAC authenticates the calling service.  It deliberately does not
stand in for the human who approves a campaign or a sensitive action.  This
module adds a second, independent RS256/OIDC check for those endpoints.
"""
import json
import os
from pathlib import Path
from uuid import UUID

from .security import AuthenticationError, Principal, RS256TokenVerifier


class HumanOIDCAuthenticator:
    def __init__(self, verifier: RS256TokenVerifier | None, scope: str, role: str,
                 *, allow_shadow_identity: bool = False):
        self.verifier = verifier
        self.scope = scope
        self.role = role
        self.allow_shadow_identity = allow_shadow_identity

    @property
    def mode(self) -> str:
        return "oidc" if self.verifier else "shadow-simulated"

    @classmethod
    def from_environment(cls, scope: str, role: str, *, shadow_mode: bool):
        default_required = "false" if shadow_mode else "true"
        required = os.getenv("ATLANTIS_REQUIRE_HUMAN_OIDC", default_required).lower() == "true"
        issuer = os.getenv("ATLANTIS_OIDC_ISSUER", "").strip()
        audience = os.getenv("ATLANTIS_OIDC_AUDIENCE", "").strip()
        keys_file = os.getenv("ATLANTIS_OIDC_PUBLIC_KEYS_FILE", "").strip()
        configured = bool(issuer and audience and keys_file)
        if required or configured:
            if not issuer or not audience or not keys_file:
                raise RuntimeError("OIDC_CONFIGURATION_REQUIRED")
            try:
                raw = json.loads(Path(keys_file).read_text(encoding="utf-8"))
                keys = {str(kid): str(pem).encode("utf-8") for kid, pem in raw.items()}
            except (OSError, ValueError, AttributeError) as exc:
                raise RuntimeError("OIDC_PUBLIC_KEYS_INVALID") from exc
            if not keys:
                raise RuntimeError("OIDC_PUBLIC_KEYS_REQUIRED")
            return cls(RS256TokenVerifier(issuer, audience, keys), scope, role)
        if not shadow_mode:
            raise RuntimeError("HUMAN_OIDC_REQUIRED_OUTSIDE_SHADOW")
        return cls(None, scope, role, allow_shadow_identity=True)

    def authenticate(self, headers: dict[str, str], tenant_id: str,
                     *, shadow_subject: str | None = None) -> Principal:
        if self.verifier:
            authorization = headers.get("authorization", "")
            if not authorization.startswith("Bearer ") or not authorization[7:].strip():
                raise AuthenticationError("OIDC_BEARER_REQUIRED")
            principal = self.verifier.verify(authorization[7:].strip())
            principal.require(self.scope, role=self.role)
        elif self.allow_shadow_identity and shadow_subject:
            principal = Principal(
                subject=shadow_subject,
                tenant_id=tenant_id,
                roles=frozenset({self.role}),
                scopes=frozenset({self.scope}),
            )
        else:
            raise AuthenticationError("HUMAN_IDENTITY_REQUIRED")
        if principal.tenant_id != tenant_id:
            raise AuthenticationError("OIDC_TENANT_MISMATCH")
        try:
            UUID(principal.subject)
        except (ValueError, TypeError, AttributeError) as exc:
            raise AuthenticationError("OIDC_SUBJECT_MUST_BE_UUID") from exc
        return principal
