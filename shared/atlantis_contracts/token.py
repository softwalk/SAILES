import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Callable

from .canonical import canonical_json


class TokenError(ValueError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


@dataclass(frozen=True)
class AuthorizationClaims:
    jti: str
    iss: str
    aud: str
    tenant_id: str
    contact_id: str
    campaign_version_id: str
    decision_id: str
    channel: str
    purpose: str
    content_hash: str
    iat: int
    exp: int


class TokenVerifier:
    """Verifies signed JIT tokens. Replay consumption is delegated to durable storage."""

    def __init__(self, secret: bytes, issuer: str, consume_jti: Callable[..., bool]):
        if len(secret) < 32:
            raise ValueError("JIT secret must contain at least 32 bytes")
        self.secret, self.issuer, self.consume_jti = secret, issuer, consume_jti

    def verify_and_consume(self, token: str, audience: str, expected: dict[str, str], now: int | None = None) -> AuthorizationClaims:
        try:
            payload_part, signature_part = token.split(".", 1)
            payload_bytes = _unb64(payload_part)
            supplied = _unb64(signature_part)
            expected_sig = hmac.new(self.secret, payload_bytes, hashlib.sha256).digest()
            if not hmac.compare_digest(supplied, expected_sig):
                raise TokenError("INVALID_SIGNATURE")
            raw = json.loads(payload_bytes)
            claims = AuthorizationClaims(**raw)
        except TokenError:
            raise
        except Exception as exc:
            raise TokenError("MALFORMED_TOKEN") from exc
        clock = int(time.time()) if now is None else now
        if claims.iss != self.issuer:
            raise TokenError("INVALID_ISSUER")
        if claims.aud != audience:
            raise TokenError("INVALID_AUDIENCE")
        if claims.exp <= clock or claims.iat > clock + 30 or claims.exp - claims.iat > 300:
            raise TokenError("TOKEN_EXPIRED_OR_INVALID_TTL")
        for key, value in expected.items():
            if getattr(claims, key, None) != value:
                raise TokenError(f"CLAIM_MISMATCH:{key}")
        if not self.consume_jti(claims.jti, claims):
            raise TokenError("TOKEN_REPLAY")
        return claims


def sign_claims(secret: bytes, claims: AuthorizationClaims) -> str:
    payload = canonical_json(claims.__dict__).encode("utf-8")
    signature = hmac.new(secret, payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(signature)}"
