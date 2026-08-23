import os
from pathlib import Path

from atlantis_contracts.http import JsonRouter
from atlantis_contracts.middleware import configure_rate_limit, configure_workload_auth
from .gateway import ModelGateway, ModelRequest, OpenAICompatibleProvider, ProviderError

router = JsonRouter(service_name="model-gateway")
configure_workload_auth(router)
configure_rate_limit(router)
router.require_idempotency("/v1/models/complete")


def configured_secret(name: str) -> str:
    file_name = os.getenv(name + "_FILE")
    if file_name:
        return Path(file_name).read_text(encoding="utf-8").strip()
    return os.getenv(name, "")


def configured_providers():
    providers = []
    for name in ("KIMI", "DEEPSEEK"):
        try:
            providers.append(OpenAICompatibleProvider(
                name.lower(), os.environ.get(f"{name}_BASE_URL", ""),
                os.environ.get(f"{name}_MODEL_ID", "UNSET"), configured_secret(f"{name}_API_KEY"),
            ))
        except ProviderError:
            pass
    return providers


@router.route("GET", "/health")
def health(_):
    return 200, {"status": "ok", "service": "model-gateway", "configured_providers": [p.name for p in configured_providers()]}


@router.route("POST", "/v1/models/complete")
def complete(body):
    try:
        request = ModelRequest(**body)
        response = ModelGateway(configured_providers(), set(filter(None, os.getenv("RESTRICTED_PROVIDER_ALLOWLIST", "").split(",")))).complete(request)
        return 200, response
    except ProviderError as exc:
        return 503, {"error": str(exc)}


if __name__ == "__main__": router.serve(int(os.getenv("PORT", "8084")))
