import os
from datetime import datetime

from atlantis_contracts import Channel, ContactabilityRequest, postgres_dsn
from atlantis_contracts.http import JsonRouter
from atlantis_contracts.middleware import configure_rate_limit, configure_workload_auth

from .authorization import AuthorizationIssuer, DecisionContextStore, InMemoryReplayLedger
from .policy import PolicyEngine
from .postgres_ledger import PostgresReplayLedger
from .decision_repository import PostgresDecisionRepository
from .evidence import EvidenceClient
from atlantis_contracts.client import JsonServiceClient


router = JsonRouter(service_name="policy-gateway")
configure_workload_auth(router)
configure_rate_limit(router)
router.require_idempotency("/v1/contactability/decisions", "/v1/outbound-authorizations")
engine = PolicyEngine()


def load_secret() -> bytes:
    secret_file = os.environ.get("ATLANTIS_JIT_SECRET_FILE")
    if secret_file:
        with open(secret_file, "rb") as source:
            return source.read().strip()
    configured = os.environ.get("ATLANTIS_JIT_SECRET")
    if configured:
        return configured.encode()
    if os.getenv("ATLANTIS_ENV", "development") == "development" and os.getenv("ATLANTIS_SHADOW_MODE", "true").lower() == "true":
        return b"development-secret-change-me-000000"
    raise RuntimeError("JIT_SECRET_REQUIRED")


secret = load_secret()
shadow_mode = os.getenv("ATLANTIS_SHADOW_MODE", "true").lower() == "true"
database_url = postgres_dsn()
evidence_url = os.getenv("ATLANTIS_CRM_EVIDENCE_URL")
evidence_client = None
if evidence_url:
    evidence_secret_file = os.getenv("ATLANTIS_EVIDENCE_WORKLOAD_SECRET_FILE")
    if not evidence_secret_file:
        raise RuntimeError("SEPARATE_EVIDENCE_WORKLOAD_SECRET_REQUIRED")
    with open(evidence_secret_file, "rb") as source:
        workload_secret = source.read().strip()
    allow_http_hosts = set(filter(None, os.getenv("ATLANTIS_SHADOW_HTTP_ALLOWLIST", "").split(","))) if shadow_mode else set()
    evidence_client = EvidenceClient(JsonServiceClient(
        evidence_url, "policy-gateway", workload_secret,
        ca_file=os.getenv("ATLANTIS_INTERNAL_CA_FILE") or None,
        client_cert_file=os.getenv("ATLANTIS_INTERNAL_CLIENT_CERT_FILE") or None,
        client_key_file=os.getenv("ATLANTIS_INTERNAL_CLIENT_KEY_FILE") or None,
        allow_http_hosts=allow_http_hosts,
    ))
elif not shadow_mode:
    raise RuntimeError("CRM_EVIDENCE_SERVICE_REQUIRED_OUTSIDE_SHADOW_MODE")
if database_url:
    ledger = PostgresReplayLedger.from_dsn(database_url)
    decision_repository = PostgresDecisionRepository.from_dsn(database_url)
elif shadow_mode:
    ledger = InMemoryReplayLedger()
    decision_repository = None
else:
    raise RuntimeError("POSTGRES_AUTHORIZATION_LEDGER_REQUIRED")
decision_max_age = int(os.getenv("ATLANTIS_DECISION_MAX_AGE_SECONDS", "120"))
issuer = AuthorizationIssuer(secret, ledger, max_decision_age_seconds=decision_max_age)
decision_contexts = DecisionContextStore(
    ttl_seconds=decision_max_age,
    max_entries=int(os.getenv("ATLANTIS_DECISION_CONTEXT_MAX_ENTRIES", "10000")),
)


@router.route("GET", "/health")
def health(_):
    return 200, {"status": "ok", "service": "policy-gateway", "shadow_mode": shadow_mode,
                 "authorization_ledger": "postgres" if database_url else "memory-dev"}


@router.route("POST", "/v1/contactability/decisions")
def decide(body):
    if evidence_client:
        body = evidence_client.resolve(body)
    body["channel"] = Channel(body["channel"])
    body["requested_at"] = datetime.fromisoformat(body["requested_at"])
    request = ContactabilityRequest(**body)
    decision = engine.decide(request)
    if decision_repository:
        decision_repository.persist(decision, request)
    decision_contexts.put(decision, request)
    return 200, decision


@router.route("POST", "/v1/outbound-authorizations")
def authorize(body):
    decision_id = body["decision_id"]
    try:
        context = decision_contexts.take(decision_id, body["tenant_id"])
        if not context:
            return 404, {"error": "DECISION_CONTEXT_NOT_FOUND"}
        decision, request = context
        token = issuer.issue(decision, request, body["audience"], int(body.get("ttl_seconds", 120)))
        return 201, {"token": token, "decision_id": decision_id}
    except PermissionError as exc:
        return 403, {"error": str(exc)}
    except ValueError as exc:
        return 400, {"error": str(exc)}


if __name__ == "__main__":
    router.serve(int(os.getenv("PORT", "8081")))
