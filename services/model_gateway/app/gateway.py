import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class ProviderError(RuntimeError): pass


class BudgetLedger:
    def __init__(self): self.spent = {}
    def remaining(self, tenant_id: str, task_alias: str, limit: int) -> int:
        return limit - self.spent.get((tenant_id, task_alias), 0)
    def charge(self, tenant_id: str, task_alias: str, units: int):
        key = tenant_id, task_alias
        self.spent[key] = self.spent.get(key, 0) + units


class ProviderHealth:
    def __init__(self): self.unhealthy = set()
    def allow(self, name): return name not in self.unhealthy
    def mark_failure(self, name): self.unhealthy.add(name)
    def mark_healthy(self, name): self.unhealthy.discard(name)


@dataclass(frozen=True)
class ModelRequest:
    tenant_id: str
    task_alias: str
    prompt: str
    data_classification: str = "INTERNAL"
    max_cost_units: int = 100
    expected_schema: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelResponse:
    provider: str
    model_id: str
    output: dict
    redaction_applied: bool
    cost_units: int


class Provider(Protocol):
    name: str
    model_id: str
    def complete(self, prompt: str) -> tuple[dict, int]: ...


class OpenAICompatibleProvider:
    def __init__(self, name: str, base_url: str, model_id: str, api_key: str):
        if not model_id or model_id == "UNSET" or not api_key:
            raise ProviderError(f"{name.upper()}_NOT_CONFIGURED")
        self.name, self.base_url, self.model_id, self.api_key = name, base_url.rstrip("/"), model_id, api_key

    def complete(self, prompt: str) -> tuple[dict, int]:
        payload = json.dumps({"model": self.model_id, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}).encode()
        request = urllib.request.Request(self.base_url + "/chat/completions", payload, {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = json.load(response)
            content = raw["choices"][0]["message"]["content"]
            usage = raw.get("usage", {})
            return json.loads(content), int(usage.get("total_tokens", 0))
        except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderError(f"{self.name.upper()}_FAILURE") from exc


class ModelGateway:
    pii_patterns = [
        re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
        re.compile(r"(?<!\d)(?:\+?52)?\s?\d{10}(?!\d)"),
    ]

    def __init__(self, providers: list[Provider], restricted_provider_allowlist: set[str] | None = None,
                 budget_ledger: BudgetLedger | None = None, health: ProviderHealth | None = None):
        self.providers = providers
        self.restricted_provider_allowlist = restricted_provider_allowlist or set()
        self.budget_ledger, self.health = budget_ledger or BudgetLedger(), health or ProviderHealth()

    def complete(self, request: ModelRequest) -> ModelResponse:
        prompt, redacted = self._redact(request.prompt)
        errors = []
        for provider in self.providers:
            if not self.health.allow(provider.name):
                continue
            if request.data_classification == "RESTRICTED" and provider.name not in self.restricted_provider_allowlist:
                continue
            if self.budget_ledger.remaining(request.tenant_id, request.task_alias, request.max_cost_units) <= 0:
                raise ProviderError("BUDGET_EXCEEDED")
            try:
                output, cost = provider.complete(prompt)
                if cost > self.budget_ledger.remaining(request.tenant_id, request.task_alias, request.max_cost_units):
                    raise ProviderError("BUDGET_EXCEEDED")
                missing = [key for key in request.expected_schema if key not in output]
                if missing:
                    raise ProviderError("INVALID_STRUCTURED_OUTPUT")
                self.budget_ledger.charge(request.tenant_id, request.task_alias, cost)
                self.health.mark_healthy(provider.name)
                return ModelResponse(provider.name, provider.model_id, output, redacted, cost)
            except ProviderError as exc:
                errors.append(str(exc))
                if "BUDGET" not in str(exc) and "INVALID_STRUCTURED" not in str(exc):
                    self.health.mark_failure(provider.name)
        raise ProviderError("NO_APPROVED_PROVIDER:" + ",".join(errors))

    def _redact(self, value: str):
        redacted = value
        for pattern in self.pii_patterns:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted, redacted != value
