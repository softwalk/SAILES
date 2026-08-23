import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODEL_SERVICE = ROOT / "services/model_gateway"
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(MODEL_SERVICE))
server = importlib.import_module("app.server")


class OpenRouterConfigurationTests(unittest.TestCase):
    def test_secret_file_takes_precedence_and_provider_order_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "openrouter-key"
            secret.write_text("file-secret", encoding="utf-8")
            environment = {
                "OPENROUTER_API_KEY": "environment-secret",
                "OPENROUTER_API_KEY_FILE": str(secret),
                "OPENROUTER_MODEL_ID": "openai/test-model",
                "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
                "ATLANTIS_MODEL_PROVIDER_ORDER": "deepseek,openrouter,kimi,openrouter",
            }
            with patch.dict(os.environ, environment, clear=True):
                providers = server.configured_providers()
        self.assertEqual([provider.name for provider in providers], ["openrouter"])
        self.assertEqual(providers[0].api_key, "file-secret")

    def test_openrouter_remains_disabled_without_explicit_model(self):
        environment = {
            "OPENROUTER_API_KEY": "configured-secret",
            "OPENROUTER_MODEL_ID": "UNSET",
            "ATLANTIS_MODEL_PROVIDER_ORDER": "openrouter",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(server.configured_providers(), [])


if __name__ == "__main__": unittest.main()
