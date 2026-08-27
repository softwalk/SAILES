import base64
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import compliance_gate


class DistributionComplianceGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.evidence = self.root / "release" / "evidence"
        self.evidence.mkdir(parents=True)
        self.artifact = self.root / "atlantis-release.tar"
        self.artifact.write_bytes(b"real-final-artifact")

    def tearDown(self):
        self.temporary.cleanup()

    def write_complete_unsigned_evidence(self):
        lock = {
            "release_status": "approved",
            "components": [{
                "name": "example", "kind": "library", "repository": "https://example.invalid/source",
                "revision": "deadbeef", "digest": "sha256:" + "1" * 64,
                "license_spdx": "Apache-2.0",
                "license_text_sha256": "", "license_path": "LICENSES/Apache-2.0.txt",
                "artifact": "example-1.0.whl", "owner": "Platform",
                "distribution_mode": "runtime-dependency", "source_obligation": "preserve-license",
            }]
        }
        sbom = {
            "bomFormat": "CycloneDX", "specVersion": "1.6",
            "components": [{
                "type": "library", "name": "example", "version": "deadbeef",
                "hashes": [{"alg": "SHA-256", "content": "1" * 64}],
                "licenses": [{"license": {"id": "Apache-2.0"}}],
            }],
        }
        spdx = {
            "spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT",
            "packages": [{
                "SPDXID": "SPDXRef-Package-example", "name": "example", "versionInfo": "deadbeef",
                "checksums": [{"algorithm": "SHA256", "checksumValue": "1" * 64}],
                "licenseDeclared": "Apache-2.0",
            }],
        }
        (self.evidence / "component-lock.json").write_text(json.dumps(lock))
        (self.evidence / "sbom.cdx.json").write_text(json.dumps(sbom))
        (self.evidence / "sbom.spdx.json").write_text(json.dumps(spdx))
        (self.evidence / "THIRD_PARTY_NOTICES.md").write_text("# Notices\n\nExample: Apache-2.0\n")
        for directory in ("LICENSES", "corresponding-source", "image-sboms"):
            target = self.evidence / directory
            target.mkdir()
            (target / "README.md").write_text(f"Evidence for {directory}\n")
        license_path = self.evidence / "LICENSES" / "Apache-2.0.txt"
        license_path.write_text("Apache License test fixture for validation only. " * 4 + "\n")
        lock["components"][0]["license_text_sha256"] = compliance_gate.sha256_file(license_path)
        (self.evidence / "component-lock.json").write_text(json.dumps(lock))
        source_manifest = {"components": [{"name": "example", "disposition": "not-required"}]}
        (self.evidence / "corresponding-source" / "manifest.json").write_text(json.dumps(source_manifest))
        image_manifest = {"scanner": {"name": "syft", "version": "1.51.0", "sha256": "0" * 64}, "images": []}
        (self.evidence / "image-sboms" / "manifest.json").write_text(json.dumps(image_manifest))

    def write_signed_attestation(self):
        artifacts = [
            {"path": relative, "sha256": compliance_gate.artifact_sha256(self.evidence / relative)}
            for relative in compliance_gate.EVIDENCE_FILES
        ]
        attestation = {
            "schema_version": 1,
            "subject": {"name": self.artifact.name, "sha256": compliance_gate.sha256_file(self.artifact)},
            "artifacts": artifacts,
            "approvals": [],
        }
        payload = compliance_gate.signed_payload(attestation)
        trust = self.root / "release" / "trusted-signers"
        trust.mkdir(parents=True)
        for role in sorted(compliance_gate.APPROVAL_ROLES):
            private_key = self.root / f"{role}.key"
            signature = self.root / f"{role}.sig"
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(trust / f"{role}.pem")],
                check=True, capture_output=True,
            )
            payload_path = self.root / "payload.json"
            payload_path.write_bytes(payload)
            subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", str(private_key), "-out", str(signature), str(payload_path)],
                check=True, capture_output=True,
            )
            attestation["approvals"].append({
                "role": role, "signer": f"{role}-test", "signed_at": "2026-08-27T00:00:00Z",
                "signature_base64": base64.b64encode(signature.read_bytes()).decode("ascii"),
            })
        (self.evidence / "attestation.json").write_text(json.dumps(attestation))

    def test_missing_evidence_is_blocked(self):
        errors = compliance_gate.distribution_errors(self.root, self.artifact)
        self.assertIn("Missing distribution artifact: release/evidence/sbom.cdx.json", errors)
        self.assertIn("Missing distribution artifact: release/evidence/attestation.json", errors)

    def test_empty_directories_are_blocked(self):
        self.write_complete_unsigned_evidence()
        for path in (self.evidence / "LICENSES").iterdir():
            path.unlink()
        errors = compliance_gate.distribution_errors(self.root, self.artifact)
        self.assertIn("Empty distribution artifact: release/evidence/LICENSES", errors)

    def test_complete_cryptographically_signed_evidence_passes(self):
        self.write_complete_unsigned_evidence()
        self.write_signed_attestation()
        self.assertEqual([], compliance_gate.distribution_errors(self.root, self.artifact))

    def test_tampering_after_signing_is_blocked(self):
        self.write_complete_unsigned_evidence()
        self.write_signed_attestation()
        with (self.evidence / "THIRD_PARTY_NOTICES.md").open("a") as stream:
            stream.write("tampered\n")
        errors = compliance_gate.distribution_errors(self.root, self.artifact)
        self.assertIn("Attestation digest mismatch: THIRD_PARTY_NOTICES.md", errors)

    def test_pending_component_is_blocked(self):
        self.write_complete_unsigned_evidence()
        lock_path = self.evidence / "component-lock.json"
        lock = json.loads(lock_path.read_text())
        lock["components"][0]["revision"] = "TBD"
        lock_path.write_text(json.dumps(lock))
        self.write_signed_attestation()
        errors = compliance_gate.distribution_errors(self.root, self.artifact)
        self.assertIn("Unpinned component: example.revision", errors)

    def test_sbom_component_missing_from_lock_is_blocked(self):
        self.write_complete_unsigned_evidence()
        sbom_path = self.evidence / "sbom.cdx.json"
        sbom = json.loads(sbom_path.read_text())
        sbom["components"].append({"type": "library", "name": "unlocked", "version": "1.0"})
        sbom_path.write_text(json.dumps(sbom))
        self.write_signed_attestation()
        errors = compliance_gate.distribution_errors(self.root, self.artifact)
        self.assertIn("SBOM component missing from component lock: unlocked", errors)

    def test_duplicate_lock_component_is_blocked(self):
        self.write_complete_unsigned_evidence()
        lock_path = self.evidence / "component-lock.json"
        lock = json.loads(lock_path.read_text())
        lock["components"].append(dict(lock["components"][0]))
        lock_path.write_text(json.dumps(lock))
        sbom_path = self.evidence / "sbom.cdx.json"
        sbom = json.loads(sbom_path.read_text())
        sbom["components"].append(dict(sbom["components"][0]))
        sbom_path.write_text(json.dumps(sbom))
        self.write_signed_attestation()
        errors = compliance_gate.distribution_errors(self.root, self.artifact)
        self.assertIn("Duplicate component in lock: example", errors)
        self.assertIn("Duplicate component in CycloneDX SBOM: example", errors)

    def test_sbom_must_match_locked_digest(self):
        self.write_complete_unsigned_evidence()
        sbom_path = self.evidence / "sbom.cdx.json"
        sbom = json.loads(sbom_path.read_text())
        sbom["components"][0]["hashes"][0]["content"] = "2" * 64
        sbom_path.write_text(json.dumps(sbom))
        self.write_signed_attestation()
        errors = compliance_gate.distribution_errors(self.root, self.artifact)
        self.assertIn("SBOM digest mismatch: example", errors)

    def test_spdx_must_match_locked_license(self):
        self.write_complete_unsigned_evidence()
        spdx_path = self.evidence / "sbom.spdx.json"
        spdx = json.loads(spdx_path.read_text())
        spdx["packages"][0]["licenseDeclared"] = "MIT"
        spdx_path.write_text(json.dumps(spdx))
        self.write_signed_attestation()
        errors = compliance_gate.distribution_errors(self.root, self.artifact)
        self.assertIn("SPDX license mismatch: example", errors)

    def test_image_sbom_unknown_license_is_blocked(self):
        self.write_complete_unsigned_evidence()
        lock_path = self.evidence / "component-lock.json"
        lock = json.loads(lock_path.read_text())
        lock["components"][0]["kind"] = "oci-image"
        lock_path.write_text(json.dumps(lock))
        image_root = self.evidence / "image-sboms"
        cdx_path = image_root / "example.cdx.json"
        spdx_path = image_root / "example.spdx.json"
        cdx_path.write_text(json.dumps({
            "bomFormat": "CycloneDX", "specVersion": "1.6",
            "components": [{"type": "library", "name": "inner", "version": "1.0"}],
        }))
        spdx_path.write_text(json.dumps({
            "spdxVersion": "SPDX-2.3", "packages": [{"name": "inner", "licenseDeclared": "NOASSERTION"}],
        }))
        manifest = {
            "scanner": {"name": "syft", "version": "1.51.0", "sha256": "0" * 64},
            "images": [{
                "name": "example", "image_id": "sha256:" + "1" * 64,
                "cyclonedx": {"path": "image-sboms/example.cdx.json", "sha256": compliance_gate.sha256_file(cdx_path)},
                "spdx": {"path": "image-sboms/example.spdx.json", "sha256": compliance_gate.sha256_file(spdx_path)},
            }],
        }
        (image_root / "manifest.json").write_text(json.dumps(manifest))
        self.write_signed_attestation()
        errors = compliance_gate.distribution_errors(self.root, self.artifact)
        self.assertIn("Unknown package license in image SBOM: example::inner", errors)

    def test_generic_license_substitution_is_blocked(self):
        self.write_complete_unsigned_evidence()
        spdx_path = self.evidence / "sbom.spdx.json"
        spdx = json.loads(spdx_path.read_text())
        spdx["packages"][0]["licenseDeclared"] = "LicenseRef-Generic-OpenSource"
        spdx_path.write_text(json.dumps(spdx))
        errors = []
        lock = compliance_gate.validate_lock(self.evidence / "component-lock.json", errors)
        compliance_gate.validate_spdx(spdx_path, lock, errors)
        self.assertIn("Unresolved SPDX declared license: example", errors)

    def test_atlantis_image_requires_published_registry_digest(self):
        self.write_complete_unsigned_evidence()
        lock_path = self.evidence / "component-lock.json"
        lock = json.loads(lock_path.read_text())
        lock["components"][0].update({
            "name": "atlantis-example", "kind": "oci-image",
            "repository": "https://github.com/softwalk/SAILES",
        })
        lock_path.write_text(json.dumps(lock))
        errors = []
        compliance_gate.validate_lock(lock_path, errors)
        self.assertIn(
            "Atlantis OCI image is not pinned to a published registry manifest: atlantis-example", errors,
        )


if __name__ == "__main__":
    unittest.main()
