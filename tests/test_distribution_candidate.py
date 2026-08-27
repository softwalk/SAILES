import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tools import generate_distribution_candidate as candidate


class DistributionCandidateTests(unittest.TestCase):
    def test_selected_wheel_must_match_locked_version_and_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            wheelhouse = Path(temporary)
            wheel = wheelhouse / "example_package-1.2.3-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(
                    "example_package-1.2.3.dist-info/METADATA",
                    "Metadata-Version: 2.4\nName: Example_Package\nVersion: 1.2.3\n",
                )
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            packages = [{"name": "example-package", "version": "1.2.3", "hashes": [digest]}]
            with mock.patch.object(candidate, "WHEELHOUSE", wheelhouse):
                manifest = candidate.select_wheels(packages, fetch=False)
            self.assertEqual(digest, packages[0]["selected_digest"])
            self.assertEqual("wheelhouse/example_package-1.2.3-py3-none-any.whl", manifest[0]["path"])

    def test_selected_wheel_outside_lock_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            wheelhouse = Path(temporary)
            wheel = wheelhouse / "example-1.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("example-1.0.dist-info/METADATA", "Name: example\nVersion: 1.0\n")
            packages = [{"name": "example", "version": "1.0", "hashes": ["0" * 64]}]
            with mock.patch.object(candidate, "WHEELHOUSE", wheelhouse):
                with self.assertRaisesRegex(ValueError, "digest is absent from runtime lock"):
                    candidate.select_wheels(packages, fetch=False)

    def test_candidate_documents_cover_every_component(self):
        components = [{
            "name": "example", "kind": "python-package", "revision": "1.0",
            "repository": "https://example.invalid", "artifact": "example.whl",
            "digest": "sha256:" + "1" * 64, "license_spdx": "MIT",
            "distribution_mode": "runtime", "source_obligation": "preserve-license",
        }]
        spdx = candidate.spdx_document(components)
        notices = candidate.notices_document(components)
        sources = candidate.source_manifest(components)
        self.assertEqual(["example"], [item["name"] for item in spdx["packages"]])
        self.assertIn("## example", notices)
        self.assertEqual(["example"], [item["name"] for item in sources["components"]])
        self.assertEqual("not-required-candidate", sources["components"][0]["disposition"])

    def test_pinned_content_rejects_a_changed_existing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "license.txt"
            path.write_text("changed")
            with self.assertRaisesRegex(ValueError, "pinned content digest mismatch"):
                candidate.pinned_content("https://example.invalid/license", "0" * 64, path, fetch=False)

    def test_image_license_gaps_are_deduplicated_across_images(self):
        manifest = {"images": [
            {"name": "one", "unknown_license_packages": [{"name": "pkg", "version": "1", "purl": "pkg:deb/pkg@1"}]},
            {"name": "two", "unknown_license_packages": [{"name": "pkg", "version": "1", "purl": "pkg:deb/pkg@1"}]},
        ]}
        report = candidate.image_license_gap_report(manifest)
        self.assertEqual(2, report["total_unknown_license_declarations"])
        self.assertEqual(1, report["unique_package_versions"])
        self.assertEqual(["one", "two"], report["packages"][0]["images"])

    def test_legal_review_queue_is_explicitly_blocked(self):
        component = {
            "name": "example", "revision": "1", "license_spdx": "MIT",
            "license_path": "LICENSES/example.txt", "license_text_sha256": "1" * 64,
            "source_obligation": "preserve-license",
        }
        inventory = [{
            "name": "dependency", "version": "2", "declared_license": "Apache-2.0",
            "license_path": "LICENSES/python/dependency.txt", "license_text_sha256": "2" * 64,
        }]
        queue = candidate.legal_review_queue([component], inventory, None)
        self.assertEqual("blocked", queue["release_status"])
        self.assertFalse(queue["legal_approval_recorded"])
        self.assertEqual("example", queue["component_declarations"][0]["name"])
        self.assertEqual("dependency", queue["python_package_declarations"][0]["name"])


if __name__ == "__main__":
    unittest.main()
