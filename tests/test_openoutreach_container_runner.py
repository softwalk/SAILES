import unittest

from tools import openoutreach_container_runner as runner


class OpenOutreachContainerRunnerTests(unittest.TestCase):
    def test_count_is_bounded_and_never_implies_paid_email_lookup(self):
        self.assertEqual(5, runner.positive_count({"count": 5}))
        for invalid in (0, 101, True, "5"):
            with self.assertRaises(ValueError):
                runner.positive_count({"count": invalid})

    def test_transform_requires_and_preserves_provenance(self):
        lead = runner.transform({
            "linkedin_url": "https://linkedin.example/person",
            "qualified_at": "2026-08-27T00:00:00+00:00",
            "first_name": "Ada", "last_name": "Lovelace", "company": "Example",
            "lead_id": "lead-1", "reason": "fit",
        })
        self.assertEqual("https://linkedin.example/person", lead["source_uri"])
        self.assertEqual("2026-08-27T00:00:00+00:00", lead["observed_at"])
        with self.assertRaisesRegex(ValueError, "lacks source provenance"):
            runner.transform({"lead_id": "missing"})

    def test_upstream_image_is_pinned_by_registry_digest(self):
        self.assertRegex(runner.IMAGE, r"^ghcr\.io/.+@sha256:[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
