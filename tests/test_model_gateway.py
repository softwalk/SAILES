import unittest
from unittest.mock import patch

from _load import load

models = load("atlantis_models", "services/model_gateway/app/gateway.py")


class FakeProvider:
    def __init__(self, name, result=None, fail=False):
        self.name, self.model_id, self.result, self.fail = name, name + "-pinned", result or {}, fail

    def complete(self, prompt, max_output_units):
        if self.fail:
            raise models.ProviderError("DOWN")
        self.last_prompt, self.last_max_output_units = prompt, max_output_units
        return self.result, 10


class ModelGatewayTests(unittest.TestCase):
    def test_fallback_and_redaction(self):
        first = FakeProvider("kimi", fail=True)
        second = FakeProvider("deepseek", {"next_action": "handoff"})
        gateway = models.ModelGateway([first, second])
        response = gateway.complete(models.ModelRequest("t1", "classify", "correo a@b.com", expected_schema=("next_action",)))
        self.assertEqual(response.provider, "deepseek")
        self.assertTrue(response.redaction_applied)
        self.assertNotIn("a@b.com", second.last_prompt)

    def test_restricted_data_blocks_unapproved_provider(self):
        gateway = models.ModelGateway([FakeProvider("kimi", {"ok": True})])
        with self.assertRaisesRegex(models.ProviderError, "NO_APPROVED_PROVIDER"):
            gateway.complete(models.ModelRequest("t1", "x", "secret", data_classification="RESTRICTED"))

    def test_openrouter_uses_tls_endpoint_and_required_headers(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self):
                return b'{"choices":[{"message":{"content":"{\\"result\\":\\"ok\\"}"}}],"usage":{"total_tokens":12}}'

        provider = models.OpenRouterProvider(
            "openai/gpt-test", "test-secret",
            http_referer="https://sales.example.com", app_title="Atlantis Tests",
        )
        with patch.object(models.urllib.request, "urlopen", return_value=Response()) as urlopen:
            output, cost = provider.complete("hola", 128)
        request = urlopen.call_args.args[0]
        payload = models.json.loads(request.data)
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(headers["authorization"], "Bearer test-secret")
        self.assertEqual(headers["http-referer"], "https://sales.example.com")
        self.assertEqual(headers["x-openrouter-title"], "Atlantis Tests")
        self.assertEqual(payload["max_completion_tokens"], 128)
        self.assertNotIn("max_tokens", payload)
        self.assertEqual((output, cost), ({"result": "ok"}, 12))

    def test_budget_is_rejected_before_provider_call(self):
        provider = FakeProvider("openrouter", {"ok": True})
        gateway = models.ModelGateway([provider])
        request = models.ModelRequest("t1", "x", "prompt too large", max_cost_units=10)
        with self.assertRaisesRegex(models.ProviderError, "BUDGET_EXCEEDED_PRECALL"):
            gateway.complete(request)
        self.assertFalse(hasattr(provider, "last_prompt"))

    def test_caller_cannot_exceed_server_budget_policy(self):
        provider = FakeProvider("openrouter", {"ok": True})
        gateway = models.ModelGateway([provider], policy_max_cost_units=1000)
        request = models.ModelRequest("t1", "x", "hello", max_cost_units=1001)
        with self.assertRaisesRegex(models.ProviderError, "BUDGET_POLICY_LIMIT_EXCEEDED"):
            gateway.complete(request)
        self.assertFalse(hasattr(provider, "last_prompt"))

    def test_provider_receives_only_remaining_budget(self):
        provider = FakeProvider("openrouter", {"ok": True})
        gateway = models.ModelGateway([provider])
        request = models.ModelRequest("t1", "x", "hello", max_cost_units=100)
        gateway.complete(request)
        self.assertEqual(provider.last_max_output_units, 31)

    def test_openrouter_rejects_non_official_or_plain_http_endpoint(self):
        for base_url in (
            "http://openrouter.ai/api/v1", "https://attacker.example/api/v1",
            "https://user:password@openrouter.ai/api/v1", "https://openrouter.ai/other",
            "https://openrouter.ai:not-a-port/api/v1",
        ):
            with self.subTest(base_url=base_url), self.assertRaisesRegex(models.ProviderError, "BASE_URL_NOT_ALLOWED"):
                models.OpenRouterProvider("openai/gpt-test", "test-secret", base_url=base_url)

    def test_openrouter_rejects_mutable_auto_model(self):
        with self.assertRaisesRegex(models.ProviderError, "MUTABLE_MODEL_NOT_ALLOWED"):
            models.OpenRouterProvider("openrouter/auto", "test-secret")

    def test_openrouter_never_receives_restricted_data_without_allowlist(self):
        provider = FakeProvider("openrouter", {"ok": True})
        gateway = models.ModelGateway([provider])
        with self.assertRaisesRegex(models.ProviderError, "NO_APPROVED_PROVIDER"):
            gateway.complete(models.ModelRequest("t1", "x", "secret", data_classification="RESTRICTED"))
        self.assertFalse(hasattr(provider, "last_prompt"))


if __name__ == "__main__": unittest.main()
