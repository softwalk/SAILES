import json
import tempfile
import unittest
from pathlib import Path

from tools import prepare_unsigned_distribution_evidence as prepare


class PrepareUnsignedEvidenceTests(unittest.TestCase):
    def test_refuses_candidate_with_blockers(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            (candidate / "BLOCKERS.json").write_text(json.dumps({"blocker_count": 1, "blockers": [{"reason": "x"}]}))
            with self.assertRaisesRegex(ValueError, "still has blockers"):
                prepare.assert_candidate_is_reviewable(candidate)

    def test_refuses_unrecorded_legal_review(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            (candidate / "BLOCKERS.json").write_text(json.dumps({"blocker_count": 0, "blockers": []}))
            (candidate / "LEGAL_REVIEW_QUEUE.json").write_text(json.dumps({"legal_approval_recorded": False}))
            with self.assertRaisesRegex(ValueError, "Legal review is not recorded"):
                prepare.assert_candidate_is_reviewable(candidate)

    def test_refuses_generic_license(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            (candidate / "image-sboms").mkdir()
            (candidate / "BLOCKERS.json").write_text(json.dumps({"blocker_count": 0, "blockers": []}))
            (candidate / "sbom.spdx.candidate.json").write_text(json.dumps({
                "packages": [{"name": "example", "licenseDeclared": "LicenseRef-Generic-OpenSource"}],
            }))
            with self.assertRaisesRegex(ValueError, "unresolved license"):
                prepare.assert_candidate_is_reviewable(candidate)


if __name__ == "__main__":
    unittest.main()
