import os

from atlantis_contracts.http import JsonRouter
from atlantis_contracts.middleware import configure_rate_limit, configure_workload_auth
from atlantis_contracts import HumanOIDCAuthenticator, postgres_dsn
from .domain import CRMStore
from .postgres import PostgresCRMRepository

router = JsonRouter(service_name="crm-api")
configure_workload_auth(router)
configure_rate_limit(router)
router.require_idempotency("/v1/contacts", "/v1/campaign-versions", "/v1/campaign-versions/approve",
                           "/v1/suppressions", "/v1/interactions",
                           "/v1/opportunities", "/v1/memory-facts", "/v1/privacy/requests", "/v1/contactability-evidence")
storage_mode = os.getenv(
    "ATLANTIS_CRM_STORAGE",
    "memory" if os.getenv("ATLANTIS_ENV", "development") == "development" else "postgres",
)
database_url = postgres_dsn()
shadow_mode = os.getenv("ATLANTIS_SHADOW_MODE", "true").lower() == "true"
if storage_mode == "postgres":
    if not database_url:
        raise RuntimeError("ATLANTIS_DATABASE_URL_REQUIRED")
    store = PostgresCRMRepository.from_dsn(database_url)
elif storage_mode == "memory" and os.getenv("ATLANTIS_SHADOW_MODE", "true").lower() == "true":
    store = CRMStore()
else:
    raise RuntimeError("POSTGRES_CRM_REQUIRED_OUTSIDE_SHADOW_MODE")
human_auth = HumanOIDCAuthenticator.from_environment(
    "campaign:approve", os.getenv("ATLANTIS_OIDC_CAMPAIGN_APPROVER_ROLE", "CAMPAIGN_APPROVER"),
    shadow_mode=shadow_mode,
)


@router.route("GET", "/health")
def health(_): return 200, {"status": "ok", "service": "crm-api", "storage": storage_mode,
                            "human_identity": human_auth.mode}


@router.route("POST", "/v1/contacts")
def contact(body): return 201, store.create_contact(body.pop("tenant_id"), body)


@router.route("POST", "/v1/campaign-versions")
def campaign(body): return 201, store.create_campaign_version(body["tenant_id"], body["campaign_id"], body["manifest"])


@router.route("POST", "/v1/campaign-versions/approve", raw=True)
def approve_campaign(request):
    body = request.json
    principal = human_auth.authenticate(
        request.headers, body["tenant_id"], shadow_subject=body.get("approver_id"),
    )
    return 200, store.approve_campaign(
        body["tenant_id"], body["campaign_version_id"], principal.subject, body["subject_hash"],
        os.getenv("ATLANTIS_OIDC_CAMPAIGN_APPROVER_ROLE", "CAMPAIGN_APPROVER"), body.get("comment"),
    )


@router.route("POST", "/v1/suppressions")
def suppress(body):
    tenant_id = body.pop("tenant_id")
    if storage_mode == "postgres":
        return 201, store.suppress(tenant_id, body)
    store.suppress(tenant_id, body["contact_id"], body.get("reason", "OPT_OUT"))
    return 201, {"status": "ACTIVE"}


@router.route("POST", "/v1/interactions")
def interaction(body):
    tenant, contact = body.pop("tenant_id"), body.pop("contact_id")
    return 201, store.record_interaction(tenant, contact, body)


@router.route("POST", "/v1/opportunities")
def opportunity(body):
    tenant, contact = body.pop("tenant_id"), body.pop("contact_id")
    return 201, store.upsert_opportunity(tenant, contact, body)


@router.route("POST", "/v1/memory-facts")
def memory_fact(body):
    tenant, contact = body.pop("tenant_id"), body.pop("contact_id")
    return 201, store.add_memory_fact(tenant, contact, body)


@router.route("POST", "/v1/privacy/requests")
def privacy_request(body):
    return 201, store.request_arco(body["tenant_id"], body["contact_id"], body["request_type"], body["identity_verification_ref"])


@router.route("POST", "/v1/contactability-evidence")
def evidence(body):
    return 200, store.contactability_evidence(body["tenant_id"], body["contact_id"], body.get("phone_token"),
                                               body["channel"], body["purpose"], body["campaign_version_id"])


if __name__ == "__main__": router.serve(int(os.getenv("PORT", "8082")))
