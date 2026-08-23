import os
from pathlib import Path
from urllib.parse import urlparse

from atlantis_contracts import TokenError, TokenVerifier, WebhookError, WebhookVerifier, postgres_dsn
from atlantis_contracts.http import JsonRouter, RawResponse
from atlantis_contracts.middleware import configure_rate_limit, configure_workload_auth
from atlantis_contracts.persistence import BoundedTTLSet
from .marketia import MarketiaAdapter
from .marketia import MarketiaTransport
from .base import HttpTransport
from .postgres_token import PostgresTokenConsumer, ShadowFirstUseConsumer
from .postgres_webhook import PostgresWebhookInbox
from .voice import NeobotTransport, VicidialTransport, VoiceAdapter
from .whatsapp import MetaCloudTransport, WhatsAppAdapter


def secret(name: str, *, required=True) -> bytes:
    file_name = os.getenv(name + "_FILE")
    value = Path(file_name).read_bytes().strip() if file_name else os.getenv(name, "").encode()
    if required and len(value) < 32:
        raise RuntimeError(name + "_REQUIRED")
    return value


def text_secret(name: str) -> str:
    file_name = os.getenv(name + "_FILE")
    return Path(file_name).read_text().strip() if file_name else os.getenv(name, "")


mode = os.getenv("ADAPTER_MODE", "marketia")
shadow = os.getenv("ATLANTIS_SHADOW_MODE", "true").lower() == "true"
dsn = postgres_dsn()
if not shadow and not dsn:
    raise RuntimeError("POSTGRES_REQUIRED_OUTSIDE_SHADOW_MODE")

consumer = PostgresTokenConsumer.from_dsn(dsn) if dsn and not shadow else ShadowFirstUseConsumer()
jit_secret = secret("ATLANTIS_JIT_SECRET", required=mode in {"voice", "whatsapp"})
verifier = TokenVerifier(jit_secret, os.getenv("ATLANTIS_TOKEN_ISSUER", "atlantis-policy-gateway"), consumer.consume) if jit_secret else None
router = JsonRouter(service_name=mode + "-adapter")
event_ids = BoundedTTLSet(
    ttl_seconds=int(os.getenv("ATLANTIS_WEBHOOK_DEDUP_TTL_SECONDS", "86400")),
    max_entries=int(os.getenv("ATLANTIS_WEBHOOK_DEDUP_MAX_ENTRIES", "20000")),
)
configure_workload_auth(router, {"/health", "/v1/webhooks/meta/whatsapp", "/v1/webhooks/vicidial", "/v1/webhooks/atlantis-neobot", "/v1/webhooks/marketia"})
configure_rate_limit(router)
router.require_idempotency("/v1/voice/calls", "/v1/whatsapp/messages", "/v1/marketia/sync")
database_url = dsn
webhook_tenant = os.getenv("ATLANTIS_WEBHOOK_TENANT_ID")
webhook_inbox = PostgresWebhookInbox.from_dsn(database_url, webhook_tenant) if database_url and webhook_tenant else None


def remember(provider, event_id, body_hash):
    if webhook_inbox: return webhook_inbox.remember(provider, event_id, body_hash)
    if not shadow: raise RuntimeError("POSTGRES_WEBHOOK_INBOX_REQUIRED")
    key = provider, event_id
    return event_ids.remember(key)


@router.route("GET", "/health")
def health(_): return 200, {"status": "ok", "service": mode + "-adapter", "shadow_mode": shadow}


if mode == "voice":
    if shadow:
        voice_transport = None
    else:
        provider_name = os.getenv("VOICE_PROVIDER", "vicidial")
        if provider_name == "vicidial":
            endpoint = os.environ["VICIDIAL_API_URL"]
            host = urlparse(endpoint).hostname
            voice_transport = VicidialTransport(HttpTransport({host}), endpoint, os.environ["VICIDIAL_API_USER"], text_secret("VICIDIAL_API_PASSWORD"))
        elif provider_name == "atlantis-neobot":
            endpoint = os.environ["NEOBOT_API_URL"]
            host = urlparse(endpoint).hostname
            voice_transport = NeobotTransport(HttpTransport({host}), endpoint, text_secret("NEOBOT_API_TOKEN"))
        else: raise RuntimeError("VOICE_PROVIDER_NOT_APPROVED")

    @router.route("POST", "/v1/voice/calls")
    def voice_call(body):
        try:
            token = body.pop("authorization_token")
            result = VoiceAdapter(verifier, voice_transport, shadow_mode=shadow).originate(token, body)
            return 202, result
        except TokenError as exc:
            return (409 if str(exc) == "TOKEN_REPLAY" else 403), {"error": str(exc)}

if mode == "whatsapp":
    if shadow:
        whatsapp_transport = None
    else:
        base_url = os.environ["META_GRAPH_BASE_URL"]
        host = urlparse(base_url).hostname
        whatsapp_transport = MetaCloudTransport(HttpTransport({host}), base_url, os.environ["META_GRAPH_VERSION"],
                                                os.environ["META_PHONE_NUMBER_ID"], text_secret("META_ACCESS_TOKEN"))
    @router.route("POST", "/v1/whatsapp/messages")
    def whatsapp_message(body):
        try:
            token = body.pop("authorization_token")
            result = WhatsAppAdapter(verifier, whatsapp_transport, shadow_mode=shadow).send(token, body)
            return 202, result
        except TokenError as exc:
            return (409 if str(exc) == "TOKEN_REPLAY" else 403), {"error": str(exc)}

    @router.route("GET", "/v1/webhooks/meta/whatsapp", raw=True)
    def meta_challenge(request):
        query = request.query
        expected = text_secret("META_WEBHOOK_VERIFY_TOKEN")
        supplied = query.get("hub.verify_token", [""])[0]
        if query.get("hub.mode", [""])[0] != "subscribe" or not expected or supplied != expected:
            return 403, {"error": "WEBHOOK_CHALLENGE_DENIED"}
        return 200, RawResponse(query.get("hub.challenge", [""])[0].encode())

    @router.route("POST", "/v1/webhooks/meta/whatsapp", raw=True)
    def meta_webhook(request):
        try:
            receipt = WebhookVerifier({"meta": secret("META_APP_SECRET")}, remember).verify_meta(
                request.body, request.headers.get("x-hub-signature-256", ""),
                request.headers.get("x-meta-event-id", ""),
            )
            return 202, receipt
        except WebhookError as exc:
            return 401, {"error": str(exc)}

if mode == "marketia":
    if shadow:
        marketia_transport = None
    else:
        base_url = os.environ["MARKETIA_BASE_URL"]
        host = urlparse(base_url).hostname
        marketia_transport = MarketiaTransport(HttpTransport({host}), base_url, text_secret("MARKETIA_API_TOKEN"))
    @router.route("POST", "/v1/marketia/sync")
    def marketia_sync(body):
        clean = MarketiaAdapter().ingest(body["payload"], body["contract_version"])
        if shadow: return 202, {"status": "SHADOW_ACCEPTED", "payload": clean}
        return 202, marketia_transport.push(body["entity_type"], body["entity_id"], body["version"], clean)


def register_generic_webhook(provider: str):
    @router.route("POST", "/v1/webhooks/" + provider, raw=True)
    def generic_webhook(request):
        try:
            secret_name = provider.upper().replace("-", "_") + "_WEBHOOK_SECRET"
            receipt = WebhookVerifier({provider: secret(secret_name)}, remember).verify_generic(
                provider, request.body, request.headers.get("x-webhook-signature", ""),
                request.headers.get("x-webhook-timestamp", ""), request.headers.get("x-webhook-event-id", ""),
            )
            return 202, receipt
        except WebhookError as exc:
            return 401, {"error": str(exc)}
    return generic_webhook


if mode == "voice":
    register_generic_webhook("vicidial")
    register_generic_webhook("atlantis-neobot")
elif mode == "marketia":
    register_generic_webhook("marketia")


if __name__ == "__main__": router.serve(int(os.getenv("PORT", {"voice": "8085", "whatsapp": "8086", "marketia": "8087"}[mode])))
