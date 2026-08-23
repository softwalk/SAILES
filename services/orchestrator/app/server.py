import os
from dataclasses import asdict

from atlantis_contracts.http import JsonRouter
from atlantis_contracts.middleware import configure_rate_limit, configure_workload_auth
from atlantis_contracts.persistence import BoundedTTLMap
from .workflow import SalesRunState, Stage, WorkflowEngine

router, engine = JsonRouter(service_name="orchestrator"), WorkflowEngine()
runs = BoundedTTLMap(
    ttl_seconds=int(os.getenv("ATLANTIS_RUN_CONTEXT_TTL_SECONDS", "86400")),
    max_entries=int(os.getenv("ATLANTIS_RUN_CONTEXT_MAX_ENTRIES", "10000")),
)
configure_workload_auth(router)
configure_rate_limit(router)
router.require_idempotency("/v1/runs", "/v1/runs/transition", "/v1/human-actions/decide")


@router.route("GET", "/health")
def health(_): return 200, {"status": "ok", "service": "orchestrator", "runtime": "deterministic-shadow"}


@router.route("POST", "/v1/runs")
def start(body):
    state = engine.start(body["tenant_id"], body["campaign_version_id"], body["contact_id"])
    runs[state.run_id] = state
    return 201, asdict(state)


@router.route("POST", "/v1/runs/transition")
def transition(body):
    state = runs[body["run_id"]]
    updated = engine.transition(state, body["event_id"], body.get("payload"))
    runs[state.run_id] = updated
    return 200, asdict(updated)


@router.route("POST", "/v1/human-actions/decide")
def decide_human(body):
    state = runs[body["run_id"]]
    updated = engine.decide_human_action(state, body["human_action_id"], body["approved"], body["actor_id"], body["subject_hash"])
    runs[state.run_id] = updated
    return 200, asdict(updated)


if __name__ == "__main__": router.serve(int(os.getenv("PORT", "8083")))
