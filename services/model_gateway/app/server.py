import os
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from atlantis_contracts import postgres_dsn
from atlantis_contracts.http import JsonRouter
from atlantis_contracts.middleware import configure_rate_limit, configure_workload_auth
from .gateway import ModelGateway, ModelRequest, OpenAICompatibleProvider, OpenRouterProvider, ProviderError
from .postgres_usage import ModelBudgetError, PostgresModelUsageRepository

router = JsonRouter(service_name="model-gateway")
configure_workload_auth(router)
configure_rate_limit(router)
router.require_idempotency("/v1/models/complete")
database_url = postgres_dsn()
usage_repository = PostgresModelUsageRepository.from_dsn(database_url) if database_url else None
if not usage_repository and os.getenv("ATLANTIS_REQUIRE_DURABLE_STATE", "false").lower() == "true":
    raise RuntimeError("POSTGRES_MODEL_USAGE_REQUIRED")


def configured_secret(name: str) -> str:
    file_name = os.getenv(name + "_FILE")
    if file_name:
        return Path(file_name).read_text(encoding="utf-8").strip()
    return os.getenv(name, "")


def configured_providers():
    available = {}
    try:
        available["openrouter"] = OpenRouterProvider(
            os.getenv("OPENROUTER_MODEL_ID", "UNSET"),
            configured_secret("OPENROUTER_API_KEY"),
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            os.getenv("OPENROUTER_HTTP_REFERER", ""),
            os.getenv("OPENROUTER_APP_TITLE", "Atlantis Autonomous Sales"),
        )
    except ProviderError:
        pass
    for name in ("KIMI", "DEEPSEEK"):
        try:
            available[name.lower()] = OpenAICompatibleProvider(
                name.lower(), os.environ.get(f"{name}_BASE_URL", ""),
                os.environ.get(f"{name}_MODEL_ID", "UNSET"), configured_secret(f"{name}_API_KEY"),
            )
        except ProviderError:
            pass
    order = os.getenv("ATLANTIS_MODEL_PROVIDER_ORDER", "openrouter,kimi,deepseek")
    names = [item.strip().lower() for item in order.split(",") if item.strip()]
    return [available[name] for name in dict.fromkeys(names) if name in available]


@router.route("GET", "/health")
def health(_):
    return 200, {"status": "ok", "service": "model-gateway", "configured_providers": [p.name for p in configured_providers()]}


@router.route("POST", "/v1/models/complete")
def complete(body):
    reservation_id = None
    request = None
    started = perf_counter()
    try:
        request = ModelRequest(**body)
        restricted = {item.strip().lower() for item in os.getenv("RESTRICTED_PROVIDER_ALLOWLIST", "").split(",") if item.strip()}
        policy_max_cost_units = int(os.getenv("ATLANTIS_MODEL_MAX_COST_UNITS_PER_REQUEST", "4000"))
        if usage_repository:
            reservation_id = usage_repository.reserve(
                request.tenant_id, request.task_alias, request.max_cost_units,
                int(os.getenv("ATLANTIS_MODEL_DAILY_BUDGET_UNITS", "100000")),
                request.run_id,
            )
        response = ModelGateway(
            configured_providers(), restricted,
            policy_max_cost_units=policy_max_cost_units,
        ).complete(request)
        result = asdict(response)
        if usage_repository:
            result["model_call_id"] = usage_repository.settle(
                reservation_id, request, actual_units=response.cost_units, provider=response.provider,
                model_id=response.model_id, latency_ms=int((perf_counter() - started) * 1000),
                outcome="SUCCESS", redaction_applied=response.redaction_applied,
            )
        return 200, result
    except (ProviderError, ValueError, ModelBudgetError) as exc:
        if usage_repository and reservation_id and request:
            usage_repository.settle(
                reservation_id, request, actual_units=0, provider="none", model_id="none",
                latency_ms=int((perf_counter() - started) * 1000), outcome=str(exc)[:128],
                redaction_applied=False,
            )
        return 503, {"error": str(exc)}


if __name__ == "__main__": router.serve(int(os.getenv("PORT", "8084")))
