#!/usr/bin/env python3
"""Fail-closed distribution gate for Atlantis client artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
lock_path = ROOT / "compliance" / "component-lock.yaml"
lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
errors: list[str] = []

required_fields = (
    "repository", "tag_or_revision", "commit", "artifact_or_model_id",
    "digest", "license_spdx", "license_text_sha256", "owner",
    "distribution_mode", "source_obligation",
)
for component in lock.get("components", []):
    for field in required_fields:
        value = str(component.get(field, "")).strip()
        if not value or value.upper() in {"TBD", "UNKNOWN", "LATEST"}:
            errors.append(f"{component.get('name', '<unknown>')}.{field} is not fixed")

required_artifacts = [
    ROOT / "compliance" / "sbom.cyclonedx.json",
    ROOT / "compliance" / "sbom.spdx.json",
    ROOT / "compliance" / "THIRD_PARTY_NOTICES.txt",
    ROOT / "compliance" / "licenses",
    ROOT / "compliance" / "corresponding-source",
    ROOT / "compliance" / "distribution-compliance-attestation.json",
]
for path in required_artifacts:
    if not path.exists():
        errors.append(f"missing distribution artifact: {path.relative_to(ROOT)}")

attestation = ROOT / "compliance" / "distribution-compliance-attestation.json"
if attestation.is_file():
    try:
        data = json.loads(attestation.read_text(encoding="utf-8"))
        for field in ("artifact_sha256", "manifest_sha256", "approved_by_release", "approved_by_security", "approved_by_legal"):
            if not data.get(field):
                errors.append(f"attestation lacks {field}")
    except Exception as exc:
        errors.append(f"invalid attestation: {exc}")

if errors:
    for error in errors:
        print(f"ERROR: {error}")
    print(f"DISTRIBUTION BLOCKED with {len(errors)} error(s)")
    sys.exit(1)
print("DISTRIBUTION GATE PASSED")
