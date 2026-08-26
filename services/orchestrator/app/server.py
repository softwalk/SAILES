import os
from dataclasses import asdict

from atlantis_contracts import HumanOIDCAuthenticator, postgres_dsn
from atlantis_contracts.http import JsonRouter
from atlantis_contracts.middleware import configure_rate_limit, configure_workload_auth
from atlantis_contracts.persistence import BoundedTTLMap
from .workflow import SalesRunState, Stage, WorkflowEngine
from .postgres_workflow import PostgresWorkflowRepository

router, engine = JsonRouter(service_name="orchestrator"), WorkflowEngine()
shadow_mode = os.getenv("ATLANTIS_SHADOW_MODE", "true").lower() == "true"
database_url = postgres_dsn()
durable_store = PostgresWorkflowRepository.from_dsn(database_url) if database_url else None
if not durable_store and os.getenv("ATLANTIS_REQUIRE_DURABLE_STATE", "false").lower() == "true":
    raise RuntimeError("POSTGRES_WORKFLOW_STORE_REQUIRED")
human_auth = HumanOIDCAuthenticator.from_environment(
    "human-action:decide", os.getenv("ATLANTIS_OIDC_HUMAN_REVIEWER_ROLE", "HUMAN_REVIEWER"),
    shadow_mode=shadow_mode,
)
runs = BoundedTTLMap(
    ttl_seconds=int(os.getenv("ATLANTIS_RUN_CONTEXT_TTL_SECONDS", "86400")),
    max_entries=int(os.getenv("ATLANTIS_RUN_CONTEXT_MAX_ENTRIES", "10000")),
)
configure_workload_auth(router)
configure_rate_limit(router)
router.require_idempotency("/v1/runs", "/v1/runs/transition", "/v1/human-actions/decide")


@router.route("GET", "/health")
def health(_): return 200, {"status": "ok", "service": "orchestrator",
                            "runtime": "postgres" if durable_store else "memory-dev",
                            "human_identity": human_auth.mode}


@router.route("POST", "/v1/runs")
def start(body):
    state = (durable_store.start(body["tenant_id"], body["campaign_version_id"], body["contact_id"])
             if durable_store else engine.start(body["tenant_id"], body["campaign_version_id"], body["contact_id"]))
    runs[state.run_id] = state
    return 201, asdict(state)


@router.route("POST", "/v1/runs/transition")
def transition(body):
    state = runs.get(body["run_id"])
    if durable_store:
        updated = durable_store.transition(body["tenant_id"], body["run_id"], body["event_id"], body.get("payload"))
    else:
        if state is None: raise ValueError("RUN_NOT_FOUND")
        updated = engine.transition(state, body["event_id"], body.get("payload"))
    runs[updated.run_id] = updated
    return 200, asdict(updated)


@router.route("POST", "/v1/human-actions/decide", raw=True)
def decide_human(request):
    body = request.json
    principal = human_auth.authenticate(
        request.headers, body["tenant_id"], shadow_subject=body.get("actor_id"),
    )
    state = runs.get(body["run_id"])
    if durable_store:
        updated = durable_store.decide_human_action(
            body["tenant_id"], body["run_id"], body["human_action_id"], body["approved"],
            principal.subject, body["subject_hash"], body.get("comment"),
        )
    else:
        if state is None: raise ValueError("RUN_NOT_FOUND")
        updated = engine.decide_human_action(
            state, body["human_action_id"], body["approved"], principal.subject, body["subject_hash"],
        )
    runs[updated.run_id] = updated
    return 200, asdict(updated)


if __name__ == "__main__": router.serve(int(os.getenv("PORT", "8083")))
