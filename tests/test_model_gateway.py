import unittest

from _load import load

models = load("atlantis_models", "services/model_gateway/app/gateway.py")


class FakeProvider:
    def __init__(self, name, result=None, fail=False):
        self.name, self.model_id, self.result, self.fail = name, name + "-pinned", result or {}, fail

    def complete(self, prompt):
        if self.fail:
            raise models.ProviderError("DOWN")
        self.last_prompt = prompt
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


if __name__ == "__main__": unittest.main()
