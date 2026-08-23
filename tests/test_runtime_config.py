import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from atlantis_contracts.config import postgres_dsn, text_secret


class RuntimeConfigTests(unittest.TestCase):
    def test_secret_file_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            path.write_text("from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {"EXAMPLE_SECRET": "from-env", "EXAMPLE_SECRET_FILE": str(path)}, clear=True):
                self.assertEqual(text_secret("EXAMPLE_SECRET"), "from-file")

    def test_postgres_dsn_escapes_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "postgres"
            path.write_text("p@ss:/word", encoding="utf-8")
            environment = {
                "ATLANTIS_DATABASE_PASSWORD_FILE": str(path),
                "ATLANTIS_DATABASE_USER": "runtime user",
                "ATLANTIS_DATABASE_HOST": "postgres",
                "ATLANTIS_DATABASE_NAME": "atlantis",
            }
            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual(postgres_dsn(), "postgresql://runtime%20user:p%40ss%3A%2Fword@postgres:5432/atlantis")

    def test_direct_dsn_is_supported_for_compatibility(self):
        with patch.dict(os.environ, {"ATLANTIS_DATABASE_URL": "postgresql://example"}, clear=True):
            self.assertEqual(postgres_dsn(), "postgresql://example")

    def test_production_requires_verify_full(self):
        environment = {
            "ATLANTIS_ENV": "production",
            "ATLANTIS_DATABASE_URL": "postgresql://db/atlantis",
            "ATLANTIS_DATABASE_SSLMODE": "require",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(RuntimeError, "VERIFY_FULL"):
                postgres_dsn()

    def test_production_adds_verify_full_and_ca(self):
        environment = {
            "ATLANTIS_ENV": "production",
            "ATLANTIS_DATABASE_URL": "postgresql://db/atlantis",
            "ATLANTIS_DATABASE_SSLROOTCERT": "/run/secrets/postgres_ca",
        }
        with patch.dict(os.environ, environment, clear=True):
            dsn = postgres_dsn()
            self.assertIn("sslmode=verify-full", dsn)
            self.assertIn("sslrootcert=%2Frun%2Fsecrets%2Fpostgres_ca", dsn)


if __name__ == "__main__":
    unittest.main()
