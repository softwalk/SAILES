#!/usr/bin/env python3
"""Fail-closed source and distribution compliance gate."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".toml", ".yaml", ".yml", ".json", ".md", ".txt"}
PENDING = {"", "TBD", "UNSET", "UNKNOWN", "LATEST", "MAIN-LATEST"}
LOCK_FIELDS = (
    "name", "kind", "repository", "revision", "artifact", "digest", "license_spdx",
    "license_text_sha256", "license_path", "owner", "distribution_mode", "source_obligation",
)
EVIDENCE_FILES = {
    "sbom.cdx.json": "file",
    "sbom.spdx.json": "file",
    "image-sboms": "directory",
    "THIRD_PARTY_NOTICES.md": "file",
    "LICENSES": "directory",
    "corresponding-source": "directory",
    "component-lock.json": "file",
}
APPROVAL_ROLES = {"release", "security", "legal"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_directory(path: Path) -> str:
    """Hash directory names and contents in stable POSIX-path order."""
    digest = hashlib.sha256()
    for item in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8") + b"\0")
        digest.update(bytes.fromhex(sha256_file(item)))
    return digest.hexdigest()


def artifact_sha256(path: Path) -> str:
    return sha256_directory(path) if path.is_dir() else sha256_file(path)


def load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid {label}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"Invalid {label}: top level must be an object")
        return None
    return data


def scan_source(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    ignored = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}
    for path in root.rglob("*"):
        if (not path.is_file() or path.suffix not in TEXT_SUFFIXES
                or "evidence" in path.parts or ignored.intersection(path.parts)):
            continue
        text = path.read_text(errors="replace")
        relative = path.relative_to(root)
        if re.search(r"(^|[\s\"'])import\s+openoutreach(?:\s|$)|from\s+openoutreach(?:\.|\s)", text, re.I):
            errors.append(f"GPL boundary violation: {relative}")
        runtime_or_manifest = relative.parts[0] in {"services", "shared", "deploy"}
        if runtime_or_manifest and re.search(r"\bn8n\b", text, re.I):
            errors.append(f"Forbidden component n8n: {relative}")
        if path.suffix == ".py" and relative.as_posix() != "tools/compliance_gate.py" and "shell=True" in text:
            errors.append(f"Unsafe subprocess shell: {relative}")
        if runtime_or_manifest and re.search(r"(?:image:|FROM)\s+[^\s]+:latest\b", text, re.I):
            errors.append(f"Mutable latest image: {relative}")
        if runtime_or_manifest and re.search(r"(?:password|secret|api_key)\s*[:=]\s*[\"'][^\"']{12,}[\"']", text, re.I):
            if "development-secret-change-me" not in text:
                errors.append(f"Possible hardcoded secret: {relative}")
    for service in ("policy_gateway", "crm_api", "orchestrator", "model_gateway", "channel_adapters"):
        if not (root / "services" / service / "Dockerfile").exists():
            errors.append(f"Missing isolated build: services/{service}/Dockerfile")
    return errors


def validate_lock(path: Path, errors: list[str]) -> dict[str, Any] | None:
    lock = load_json(path, "component lock", errors)
    if lock is None:
        return None
    if lock.get("release_status") != "approved":
        errors.append("Invalid component lock: release_status must be approved")
    components = lock.get("components")
    if not isinstance(components, list) or not components:
        errors.append("Invalid component lock: components must be a non-empty array")
        return lock
    seen_names: set[str] = set()
    for index, item in enumerate(components):
        if not isinstance(item, dict):
            errors.append(f"Invalid component lock: components[{index}] must be an object")
            continue
        name = str(item.get("name", f"components[{index}]")).strip()
        normalized_name = name.casefold()
        if normalized_name in seen_names:
            errors.append(f"Duplicate component in lock: {name}")
        seen_names.add(normalized_name)
        for field in LOCK_FIELDS:
            value = str(item.get(field, "")).strip()
            if value.upper() in PENDING:
                errors.append(f"Unpinned component: {name}.{field}")
        digest = str(item.get("digest", ""))
        if digest and not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            errors.append(f"Invalid component digest: {name}")
        license_digest = str(item.get("license_text_sha256", ""))
        if license_digest and license_digest.upper() not in PENDING and not re.fullmatch(r"[0-9a-f]{64}", license_digest):
            errors.append(f"Invalid license digest: {name}")
        combined = json.dumps(item, sort_keys=True)
        if re.search(r"(?:^|[/:@-])latest(?:$|[/:@-])", combined, re.I):
            errors.append(f"Mutable component reference: {name}")
        if re.search(r"\bn8n\b", combined, re.I):
            errors.append(f"Forbidden component in lock: {name}")
    return lock


def validate_licenses(evidence: Path, lock: dict[str, Any] | None, errors: list[str]) -> None:
    if not lock:
        return
    license_root = (evidence / "LICENSES").resolve()
    for item in lock.get("components", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "<unknown>"))
        relative = str(item.get("license_path", ""))
        target = (evidence / relative).resolve()
        try:
            target.relative_to(license_root)
        except ValueError:
            errors.append(f"License path escapes LICENSES directory: {name}")
            continue
        if not target.is_file() or target.stat().st_size == 0:
            errors.append(f"Missing license text for component: {name}")
        elif sha256_file(target) != item.get("license_text_sha256"):
            errors.append(f"License text digest mismatch: {name}")


def validate_notices(evidence: Path, lock: dict[str, Any] | None, errors: list[str]) -> None:
    if not lock:
        return
    notices = (evidence / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace").casefold()
    for item in lock.get("components", []):
        name = str(item.get("name", "")).strip()
        if name and name.casefold() not in notices:
            errors.append(f"Component missing from third-party notices: {name}")


def validate_corresponding_source(evidence: Path, lock: dict[str, Any] | None, errors: list[str]) -> None:
    manifest_path = evidence / "corresponding-source" / "manifest.json"
    manifest = load_json(manifest_path, "corresponding-source manifest", errors)
    if manifest is None or not lock:
        return
    entries = manifest.get("components")
    if not isinstance(entries, list):
        errors.append("Corresponding-source manifest components must be an array")
        return
    names = [str(item.get("name", "")) for item in entries if isinstance(item, dict)]
    for name in sorted({name for name in names if name and names.count(name) > 1}):
        errors.append(f"Duplicate component in corresponding-source manifest: {name}")
    by_name = {str(item.get("name")): item for item in entries if isinstance(item, dict)}
    for component in lock.get("components", []):
        name = str(component.get("name", ""))
        entry = by_name.get(name)
        if entry is None:
            errors.append(f"Component missing from corresponding-source manifest: {name}")
            continue
        disposition = entry.get("disposition")
        if disposition not in {"included", "written-offer", "not-required"}:
            errors.append(f"Invalid corresponding-source disposition: {name}")
            continue
        obligation = str(component.get("source_obligation", "")).casefold()
        if disposition == "not-required" and any(marker in obligation for marker in ("include", "source-offer", "corresponding-source")):
            errors.append(f"Corresponding source is required by component obligation: {name}")
            continue
        if disposition in {"included", "written-offer"}:
            relative = str(entry.get("path", ""))
            target = (manifest_path.parent / relative).resolve()
            try:
                target.relative_to(manifest_path.parent.resolve())
            except ValueError:
                errors.append(f"Corresponding-source path escapes evidence directory: {name}")
                continue
            if not target.exists() or (target.is_file() and target.stat().st_size == 0):
                errors.append(f"Missing corresponding-source material: {name}")
            elif entry.get("sha256") != artifact_sha256(target):
                errors.append(f"Corresponding-source digest mismatch: {name}")


def validate_sbom(path: Path, lock: dict[str, Any] | None, errors: list[str]) -> None:
    sbom = load_json(path, "CycloneDX SBOM", errors)
    if sbom is None:
        return
    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.6":
        errors.append("Invalid CycloneDX SBOM header")
    components = sbom.get("components")
    if not isinstance(components, list) or not components:
        errors.append("CycloneDX SBOM has no components")
        return
    sbom_name_list = [str(item.get("name", "")).casefold() for item in components if isinstance(item, dict)]
    for name in sorted({name for name in sbom_name_list if name and sbom_name_list.count(name) > 1}):
        errors.append(f"Duplicate component in CycloneDX SBOM: {name}")
    serialized = json.dumps(components, sort_keys=True)
    if re.search(r"\bn8n\b", serialized, re.I):
        errors.append("Forbidden component in CycloneDX SBOM: n8n")
    if lock:
        sbom_names = set(sbom_name_list)
        lock_names = {str(item.get("name", "")).casefold() for item in lock.get("components", []) if isinstance(item, dict)}
        sbom_by_name = {
            str(item.get("name", "")).casefold(): item for item in components if isinstance(item, dict)
        }
        for item in lock.get("components", []):
            name = str(item.get("name", ""))
            if name and name.casefold() not in sbom_names:
                errors.append(f"Component missing from CycloneDX SBOM: {name}")
                continue
            sbom_item = sbom_by_name[name.casefold()]
            if str(sbom_item.get("version", "")) != str(item.get("revision", "")):
                errors.append(f"SBOM revision mismatch: {name}")
            expected_digest = str(item.get("digest", "")).removeprefix("sha256:")
            hashes = sbom_item.get("hashes", [])
            sbom_hashes = {
                str(entry.get("content", "")) for entry in hashes
                if isinstance(entry, dict) and str(entry.get("alg", "")).upper() in {"SHA-256", "SHA_256"}
            } if isinstance(hashes, list) else set()
            if expected_digest not in sbom_hashes:
                errors.append(f"SBOM digest mismatch: {name}")
            licenses = sbom_item.get("licenses", [])
            declared = set()
            if isinstance(licenses, list):
                for choice in licenses:
                    if not isinstance(choice, dict):
                        continue
                    if choice.get("expression"):
                        declared.add(str(choice["expression"]))
                    license_data = choice.get("license")
                    if isinstance(license_data, dict) and license_data.get("id"):
                        declared.add(str(license_data["id"]))
            if str(item.get("license_spdx", "")) not in declared:
                errors.append(f"SBOM license mismatch: {name}")
        for item in components:
            name = str(item.get("name", "")) if isinstance(item, dict) else ""
            if name and name.casefold() not in lock_names:
                errors.append(f"SBOM component missing from component lock: {name}")


def validate_spdx(path: Path, lock: dict[str, Any] | None, errors: list[str]) -> None:
    sbom = load_json(path, "SPDX SBOM", errors)
    if sbom is None:
        return
    if (sbom.get("spdxVersion") != "SPDX-2.3" or sbom.get("dataLicense") != "CC0-1.0"
            or sbom.get("SPDXID") != "SPDXRef-DOCUMENT"):
        errors.append("Invalid SPDX SBOM header")
    packages = sbom.get("packages")
    if not isinstance(packages, list) or not packages:
        errors.append("SPDX SBOM has no packages")
        return
    names = [str(item.get("name", "")).casefold() for item in packages if isinstance(item, dict)]
    for name in sorted({name for name in names if name and names.count(name) > 1}):
        errors.append(f"Duplicate package in SPDX SBOM: {name}")
    if not lock:
        return
    by_name = {str(item.get("name", "")).casefold(): item for item in packages if isinstance(item, dict)}
    lock_names = {str(item.get("name", "")).casefold() for item in lock.get("components", []) if isinstance(item, dict)}
    for component in lock.get("components", []):
        name = str(component.get("name", ""))
        package = by_name.get(name.casefold())
        if package is None:
            errors.append(f"Component missing from SPDX SBOM: {name}")
            continue
        if str(package.get("versionInfo", "")) != str(component.get("revision", "")):
            errors.append(f"SPDX revision mismatch: {name}")
        expected_digest = str(component.get("digest", "")).removeprefix("sha256:")
        checksums = package.get("checksums", [])
        actual = {
            str(entry.get("checksumValue", "")) for entry in checksums
            if isinstance(entry, dict) and entry.get("algorithm") == "SHA256"
        } if isinstance(checksums, list) else set()
        if expected_digest not in actual:
            errors.append(f"SPDX digest mismatch: {name}")
        if package.get("licenseDeclared") != component.get("license_spdx"):
            errors.append(f"SPDX license mismatch: {name}")
    for package in packages:
        name = str(package.get("name", "")) if isinstance(package, dict) else ""
        if name and name.casefold() not in lock_names:
            errors.append(f"SPDX package missing from component lock: {name}")


def validate_image_sboms(evidence: Path, lock: dict[str, Any] | None, errors: list[str]) -> None:
    manifest_path = evidence / "image-sboms" / "manifest.json"
    manifest = load_json(manifest_path, "image SBOM manifest", errors)
    if manifest is None or not lock:
        return
    scanner = manifest.get("scanner")
    scanner_digest = str(scanner.get("sha256", "")) if isinstance(scanner, dict) else ""
    if (not isinstance(scanner, dict) or not str(scanner.get("name", "")).strip()
            or str(scanner.get("version", "")).upper() in PENDING
            or not re.fullmatch(r"[0-9a-f]{64}", scanner_digest)):
        errors.append("Image SBOM manifest lacks a fixed scanner version")
    images = manifest.get("images")
    if not isinstance(images, list):
        errors.append("Image SBOM manifest images must be an array")
        return
    names = [str(item.get("name", "")).casefold() for item in images if isinstance(item, dict)]
    for duplicate in sorted({name for name in names if name and names.count(name) > 1}):
        errors.append(f"Duplicate image in SBOM manifest: {duplicate}")
    by_name = {str(item.get("name", "")).casefold(): item for item in images if isinstance(item, dict)}
    oci_components = {
        str(item.get("name", "")).casefold(): item for item in lock.get("components", [])
        if isinstance(item, dict) and item.get("kind") == "oci-image"
    }
    image_root = manifest_path.parent.resolve()
    for name, component in oci_components.items():
        entry = by_name.get(name)
        display_name = str(component.get("name", name))
        if entry is None:
            errors.append(f"OCI component missing image SBOMs: {display_name}")
            continue
        if entry.get("image_id") != component.get("digest"):
            errors.append(f"Image SBOM digest mismatch: {display_name}")
        for format_name, expected_header, collection in (
            ("cyclonedx", ("bomFormat", "CycloneDX"), "components"),
            ("spdx", ("spdxVersion", "SPDX-2.3"), "packages"),
        ):
            descriptor = entry.get(format_name)
            if not isinstance(descriptor, dict):
                errors.append(f"Missing {format_name} image SBOM descriptor: {display_name}")
                continue
            target = (evidence / str(descriptor.get("path", ""))).resolve()
            try:
                target.relative_to(image_root)
            except ValueError:
                errors.append(f"Image SBOM path escapes evidence directory: {display_name}")
                continue
            if not target.is_file() or target.stat().st_size == 0:
                errors.append(f"Missing {format_name} image SBOM: {display_name}")
                continue
            if descriptor.get("sha256") != sha256_file(target):
                errors.append(f"Image SBOM file digest mismatch: {display_name}.{format_name}")
                continue
            data = load_json(target, f"{display_name} {format_name} image SBOM", errors)
            if data is None:
                continue
            header_field, header_value = expected_header
            if data.get(header_field) != header_value or not isinstance(data.get(collection), list) or not data[collection]:
                errors.append(f"Invalid {format_name} image SBOM content: {display_name}")
            serialized = json.dumps(data.get(collection, []), sort_keys=True)
            if re.search(r"\bn8n\b", serialized, re.I):
                errors.append(f"Forbidden component in image SBOM: {display_name}")
            if format_name == "spdx":
                unknown = [
                    str(package.get("name", "<unknown>")) for package in data.get("packages", [])
                    if isinstance(package, dict) and package.get("licenseDeclared") in {None, "", "NOASSERTION"}
                ]
                for package in unknown:
                    errors.append(f"Unknown package license in image SBOM: {display_name}::{package}")
    for name in sorted(set(by_name) - set(oci_components)):
        errors.append(f"Image SBOM is absent from component lock: {name}")


def signed_payload(attestation: dict[str, Any]) -> bytes:
    payload = {"subject": attestation.get("subject"), "artifacts": attestation.get("artifacts")}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_approval(root: Path, approval: dict[str, Any], payload: bytes, errors: list[str]) -> None:
    role = str(approval.get("role", "")).casefold()
    signer = str(approval.get("signer", "")).strip()
    signed_at = str(approval.get("signed_at", "")).strip()
    encoded = str(approval.get("signature_base64", "")).strip()
    if role not in APPROVAL_ROLES or not signer or not signed_at or not encoded:
        errors.append(f"Invalid {role or 'unknown'} approval metadata")
        return
    try:
        parsed_signed_at = datetime.fromisoformat(signed_at.replace("Z", "+00:00"))
        if parsed_signed_at.tzinfo is None or parsed_signed_at > datetime.now(UTC):
            raise ValueError
    except ValueError:
        errors.append(f"Invalid signed_at timestamp for {role}")
        return
    key = root / "release" / "trusted-signers" / f"{role}.pem"
    if not key.is_file():
        errors.append(f"Missing trusted signer key: release/trusted-signers/{role}.pem")
        return
    try:
        signature = base64.b64decode(encoded, validate=True)
    except ValueError:
        errors.append(f"Invalid base64 signature for {role}")
        return
    try:
        with tempfile.TemporaryDirectory(prefix="atlantis-attestation-") as temporary:
            temp = Path(temporary)
            payload_path = temp / "payload.json"
            signature_path = temp / "signature.bin"
            payload_path.write_bytes(payload)
            signature_path.write_bytes(signature)
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", str(key), "-signature", str(signature_path), str(payload_path)],
                capture_output=True, text=True, check=False,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"Could not verify {role} signature: {exc}")
        return
    if result.returncode != 0:
        errors.append(f"Invalid cryptographic signature for {role}")


def validate_attestation(root: Path, evidence: Path, artifact: Path | None, errors: list[str]) -> None:
    attestation = load_json(evidence / "attestation.json", "attestation", errors)
    if attestation is None:
        return
    if attestation.get("schema_version") != 1:
        errors.append("Invalid attestation schema_version")
    subject = attestation.get("subject")
    if artifact is None:
        errors.append("Final distribution artifact was not supplied with --artifact")
    elif not artifact.is_file() or artifact.stat().st_size == 0:
        errors.append(f"Final distribution artifact is missing or empty: {artifact}")
    elif (not isinstance(subject, dict) or not str(subject.get("name", "")).strip()
          or subject.get("sha256") != sha256_file(artifact)):
        errors.append("Attestation subject digest does not match final distribution artifact")

    recorded = attestation.get("artifacts")
    if not isinstance(recorded, list):
        errors.append("Attestation artifacts must be an array")
    else:
        artifact_paths = [str(item.get("path")) for item in recorded if isinstance(item, dict)]
        for duplicate in sorted({name for name in artifact_paths if artifact_paths.count(name) > 1}):
            errors.append(f"Duplicate artifact in attestation: {duplicate}")
        by_path = {str(item.get("path")): item for item in recorded if isinstance(item, dict)}
        for relative in EVIDENCE_FILES:
            item = by_path.get(relative)
            target = evidence / relative
            if item is None:
                errors.append(f"Attestation does not bind artifact: {relative}")
            elif item.get("sha256") != artifact_sha256(target):
                errors.append(f"Attestation digest mismatch: {relative}")

    approvals = attestation.get("approvals")
    if not isinstance(approvals, list):
        errors.append("Attestation approvals must be an array")
        return
    roles = {str(item.get("role", "")).casefold() for item in approvals if isinstance(item, dict)}
    role_list = [str(item.get("role", "")).casefold() for item in approvals if isinstance(item, dict)]
    for duplicate in sorted({role for role in role_list if role and role_list.count(role) > 1}):
        errors.append(f"Duplicate attestation approval: {duplicate}")
    for missing in sorted(APPROVAL_ROLES - roles):
        errors.append(f"Missing attestation approval: {missing}")
    payload = signed_payload(attestation)
    for approval in approvals:
        if isinstance(approval, dict):
            verify_approval(root, approval, payload, errors)


def distribution_errors(root: Path = ROOT, artifact: Path | None = None) -> list[str]:
    errors: list[str] = []
    evidence = root / "release" / "evidence"
    for relative, kind in EVIDENCE_FILES.items():
        path = evidence / relative
        valid = path.is_file() if kind == "file" else path.is_dir()
        if not valid:
            errors.append(f"Missing distribution artifact: {path.relative_to(root)}")
        elif (path.stat().st_size == 0 if path.is_file() else not any(item.is_file() for item in path.rglob("*"))):
            errors.append(f"Empty distribution artifact: {path.relative_to(root)}")
    attestation_path = evidence / "attestation.json"
    if not attestation_path.is_file():
        errors.append(f"Missing distribution artifact: {attestation_path.relative_to(root)}")
    if errors:
        return errors
    lock = validate_lock(evidence / "component-lock.json", errors)
    validate_sbom(evidence / "sbom.cdx.json", lock, errors)
    validate_spdx(evidence / "sbom.spdx.json", lock, errors)
    validate_image_sboms(evidence, lock, errors)
    validate_licenses(evidence, lock, errors)
    validate_notices(evidence, lock, errors)
    validate_corresponding_source(evidence, lock, errors)
    validate_attestation(root, evidence, artifact, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["source", "distribution"], default="source")
    parser.add_argument("--artifact", type=Path, help="final client artifact bound by the attestation")
    args = parser.parse_args()
    errors = scan_source()
    if args.mode == "distribution":
        artifact = args.artifact.resolve() if args.artifact else None
        errors += distribution_errors(artifact=artifact)
    if errors:
        print("COMPLIANCE GATE: BLOCKED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"COMPLIANCE GATE: PASS ({args.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
