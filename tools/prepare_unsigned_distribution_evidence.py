#!/usr/bin/env python3
"""Prepare reviewed distribution evidence without creating keys or approvals."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "release" / "candidate" / "distribution"
DEFAULT_OUTPUT = ROOT / "release" / "unsigned-evidence"
COPIED_DIRECTORIES = ("LICENSES", "image-sboms", "corresponding-source")
COPIED_FILES = {
    "sbom.cdx.candidate.json": "sbom.cdx.json",
    "sbom.spdx.candidate.json": "sbom.spdx.json",
    "THIRD_PARTY_NOTICES.candidate.md": "THIRD_PARTY_NOTICES.md",
    "component-lock.candidate.json": "component-lock.json",
}
ATTESTED = {
    "sbom.cdx.json": "file", "sbom.spdx.json": "file", "image-sboms": "directory",
    "THIRD_PARTY_NOTICES.md": "file", "LICENSES": "directory",
    "corresponding-source": "directory", "component-lock.json": "file",
}
UNRESOLVED_LICENSES = {
    "", "NOASSERTION", "NONE", "UNKNOWN", "TBD", "LICENSEREF-GENERIC-OPENSOURCE",
    "LICENSEREF-UNKNOWN", "LICENSEREF-UNSPECIFIED",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_directory(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(item.relative_to(path).as_posix().encode() + b"\0")
        digest.update(bytes.fromhex(sha256_file(item)))
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def assert_candidate_is_reviewable(candidate: Path) -> None:
    blockers = load_object(candidate / "BLOCKERS.json")
    if blockers.get("blocker_count") != 0 or blockers.get("blockers"):
        raise ValueError("candidate still has blockers; evidence preparation refused")
    queue_path = candidate / "LEGAL_REVIEW_QUEUE.json"
    if queue_path.is_file():
        queue = load_object(queue_path)
        if not queue.get("legal_approval_recorded"):
            raise ValueError("Legal review is not recorded; evidence preparation refused")
    for path in [candidate / "sbom.spdx.candidate.json", *(candidate / "image-sboms").glob("*.spdx.json")]:
        document = load_object(path)
        for package in document.get("packages", []):
            if not isinstance(package, dict):
                continue
            for field in ("licenseDeclared", "licenseConcluded"):
                value = package.get(field)
                if value is not None and str(value).strip().upper() in UNRESOLVED_LICENSES:
                    raise ValueError(f"unresolved license in {path.name}: {package.get('name', '<unknown>')}.{field}")


def prepare(candidate: Path, output: Path, artifact: Path) -> Path:
    assert_candidate_is_reviewable(candidate)
    if output.exists():
        raise FileExistsError(f"output already exists: {output}; review and remove it explicitly")
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise ValueError("final artifact is missing or empty")

    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        raise FileExistsError(f"staging output already exists: {staging}")
    staging.mkdir(parents=True)
    try:
        for name in COPIED_DIRECTORIES:
            shutil.copytree(candidate / name, staging / name)
        candidate_image_manifest = staging / "image-sboms" / "manifest.candidate.json"
        if candidate_image_manifest.is_file():
            candidate_image_manifest.rename(staging / "image-sboms" / "manifest.json")
        candidate_source_manifest = staging / "corresponding-source" / "manifest.candidate.json"
        if candidate_source_manifest.is_file():
            candidate_source_manifest.rename(staging / "corresponding-source" / "manifest.json")
        for source, destination in COPIED_FILES.items():
            shutil.copy2(candidate / source, staging / destination)

        lock_path = staging / "component-lock.json"
        lock = load_object(lock_path)
        if lock.get("release_status") != "approved":
            raise ValueError("reviewed component lock must already have release_status=approved")

        artifacts = []
        for relative, kind in sorted(ATTESTED.items()):
            path = staging / relative
            digest = sha256_directory(path) if kind == "directory" else sha256_file(path)
            artifacts.append({"path": relative, "kind": kind, "sha256": digest})
        attestation = {
            "schema_version": 1,
            "subject": {"name": artifact.name, "sha256": sha256_file(artifact)},
            "artifacts": artifacts,
            "approvals": [],
        }
        (staging / "attestation.unsigned.json").write_text(
            json.dumps(attestation, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        payload = {"subject": attestation["subject"], "artifacts": attestation["artifacts"]}
        (staging / "SIGNING_PAYLOAD.json").write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False), encoding="utf-8",
        )
        staging.rename(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = prepare(args.candidate.resolve(), args.output.resolve(), args.artifact.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: unsigned evidence prepared at {output}")
    print("Release, Security and Legal must sign SIGNING_PAYLOAD.json independently.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

