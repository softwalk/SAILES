import hashlib
import hmac
import time
from dataclasses import dataclass


class WebhookError(ValueError): pass


@dataclass(frozen=True)
class VerifiedWebhook:
    provider: str
    event_id: str
    body_hash: str
    received_at: int


class WebhookVerifier:
    def __init__(self, secrets: dict[str, bytes], remember_event, max_skew_seconds=300):
        self.secrets = secrets
        self.remember_event = remember_event
        self.max_skew_seconds = max_skew_seconds

    def verify_meta(self, raw_body: bytes, signature: str, event_id: str, now=None) -> VerifiedWebhook:
        secret = self._secret("meta")
        expected = "sha256=" + hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise WebhookError("INVALID_META_SIGNATURE")
        return self._accept("meta", event_id, raw_body, int(time.time()) if now is None else now)

    def verify_generic(self, provider: str, raw_body: bytes, signature: str, timestamp: str, event_id: str, now=None) -> VerifiedWebhook:
        clock = int(time.time()) if now is None else now
        try:
            signed_at = int(timestamp)
        except ValueError as exc:
            raise WebhookError("INVALID_WEBHOOK_TIMESTAMP") from exc
        if abs(clock - signed_at) > self.max_skew_seconds:
            raise WebhookError("STALE_WEBHOOK")
        expected = hmac.new(self._secret(provider), timestamp.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise WebhookError("INVALID_WEBHOOK_SIGNATURE")
        return self._accept(provider, event_id, raw_body, clock)

    def _secret(self, provider):
        secret = self.secrets.get(provider)
        if not secret or len(secret) < 32:
            raise WebhookError("WEBHOOK_SECRET_NOT_CONFIGURED")
        return secret

    def _accept(self, provider, event_id, body, now):
        if not event_id:
            raise WebhookError("WEBHOOK_EVENT_ID_REQUIRED")
        body_hash = hashlib.sha256(body).hexdigest()
        if not self.remember_event(provider, event_id, body_hash):
            raise WebhookError("DUPLICATE_WEBHOOK")
        return VerifiedWebhook(provider, event_id, body_hash, now)
