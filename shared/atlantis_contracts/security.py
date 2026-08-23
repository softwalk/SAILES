import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


class AuthenticationError(PermissionError): pass
class AuthorizationError(PermissionError): pass


def _decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    roles: frozenset[str]
    scopes: frozenset[str]

    def require(self, scope: str, *, role: str | None = None):
        if scope not in self.scopes or (role and role not in self.roles):
            raise AuthorizationError("INSUFFICIENT_PRIVILEGES")


class RS256TokenVerifier:
    """Offline OIDC access-token verifier using an allowlisted, pre-fetched key set."""

    def __init__(self, issuer: str, audience: str, public_keys: dict[str, bytes], clock_skew=30):
        self.issuer, self.audience, self.public_keys, self.clock_skew = issuer, audience, public_keys, clock_skew

    def verify(self, token: str, now: int | None = None) -> Principal:
        try:
            header_part, payload_part, signature_part = token.split(".")
            header, payload = json.loads(_decode(header_part)), json.loads(_decode(payload_part))
            if header.get("alg") != "RS256" or header.get("typ", "JWT") != "JWT":
                raise AuthenticationError("JWT_ALGORITHM_DENIED")
            key_bytes = self.public_keys[header["kid"]]
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            key = serialization.load_pem_public_key(key_bytes)
            key.verify(_decode(signature_part), f"{header_part}.{payload_part}".encode(), padding.PKCS1v15(), hashes.SHA256())
        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError("INVALID_ACCESS_TOKEN") from exc
        clock = int(time.time()) if now is None else now
        audience = payload.get("aud", [])
        audience = [audience] if isinstance(audience, str) else audience
        if payload.get("iss") != self.issuer or self.audience not in audience:
            raise AuthenticationError("JWT_ISSUER_OR_AUDIENCE_MISMATCH")
        if int(payload.get("exp", 0)) <= clock - self.clock_skew or int(payload.get("nbf", 0)) > clock + self.clock_skew:
            raise AuthenticationError("JWT_TIME_INVALID")
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise AuthenticationError("JWT_TENANT_MISSING")
        scopes = payload.get("scope", "").split()
        roles = payload.get("roles", [])
        return Principal(payload.get("sub", ""), tenant_id, frozenset(roles), frozenset(scopes))


class WorkloadRequestVerifier:
    """HMAC request authentication for internal services; use mTLS additionally in production."""

    def __init__(self, secrets: dict[str, bytes], remember_nonce, max_skew_seconds=60):
        self.secrets, self.remember_nonce, self.max_skew_seconds = secrets, remember_nonce, max_skew_seconds

    def verify(self, service_id: str, timestamp: str, nonce: str, signature: str, method: str, path: str,
               body: bytes, tenant_id: str, now=None):
        secret = self.secrets.get(service_id)
        if not secret or len(secret) < 32:
            raise AuthenticationError("WORKLOAD_NOT_CONFIGURED")
        clock = int(time.time()) if now is None else now
        try: issued = int(timestamp)
        except ValueError as exc: raise AuthenticationError("WORKLOAD_TIMESTAMP_INVALID") from exc
        if abs(clock - issued) > self.max_skew_seconds:
            raise AuthenticationError("WORKLOAD_SIGNATURE_STALE")
        body_hash = hashlib.sha256(body).hexdigest()
        canonical = "\n".join((timestamp, nonce, method.upper(), path, body_hash)).encode()
        expected = hmac.new(secret, canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise AuthenticationError("WORKLOAD_SIGNATURE_INVALID")
        if not tenant_id:
            raise AuthenticationError("WORKLOAD_TENANT_REQUIRED")
        if not self.remember_nonce(service_id, nonce, tenant_id, issued):
            raise AuthenticationError("WORKLOAD_REPLAY")
        return service_id


def sign_workload_request(secret: bytes, timestamp: int, nonce: str, method: str, path: str, body: bytes) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((str(timestamp), nonce, method.upper(), path, body_hash)).encode()
    return hmac.new(secret, canonical, hashlib.sha256).hexdigest()
