#!/usr/bin/env python3
"""Generate deterministic, non-releasable distribution evidence candidates."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release" / "candidate" / "distribution"
SPEC_LOCK = ROOT / "spec" / "compliance" / "component-lock.yaml"
RUNTIME_LOCK = ROOT / "deploy" / "proxmox" / "base" / "requirements-runtime.lock"
PENDING = {"", "TBD", "UNKNOWN", "UNSET", "LATEST", "MAIN-LATEST"}
SERVICE_IMAGES = (
    "atlantis-policy-gateway:0.9.0-rc5",
    "atlantis-crm-api:0.9.0-rc5",
    "atlantis-orchestrator:0.9.0-rc5",
    "atlantis-model-gateway:0.9.0-rc5",
    "atlantis-voice-adapter:0.9.0-rc5",
    "atlantis-whatsapp-adapter:0.9.0-rc5",
    "atlantis-marketia-adapter:0.9.0-rc5",
)
PYTHON_BASE_IMAGE = "atlantis-python-base:0.9.0-rc5"
WHEELHOUSE = OUT / "wheelhouse"
THIRD_PARTY_IMAGES = {
    "python-runtime": "python:3.12-slim-bookworm",
    "postgresql": "postgres:16-bookworm",
    "keycloak-shadow-validation": "quay.io/keycloak/keycloak@sha256:831330513f55695572286e521f94fcd3c7e285250ed5b848090265a33192f669",
    "rabbitmq": "rabbitmq:3.13-management-alpine",
    "valkey": "valkey/valkey:8-alpine",
    "litellm": "ghcr.io/berriai/litellm:main-latest",
    "node-red": "nodered/node-red:4.0.9-22-minimal",
    "prometheus": "prom/prometheus:v2.54.1",
    "grafana": "grafana/grafana:11.2.0",
    "opentelemetry-collector": "otel/opentelemetry-collector-contrib:0.108.0",
    "caddy": "caddy:2.8.4-alpine",
}
PINNED_SOURCE_REVISIONS = {
    "python-runtime": {"revision": "2abcf904b8dac8c999d2b3aac76681abb333798a", "evidence": "runtime-version:3.12.14+git-tag:v3.12.14"},
    "postgresql": {"revision": "7d3e000c5961a544302072058a1184e9a588837b", "evidence": "runtime-version:16.15+git-tag:REL_16_15"},
    "rabbitmq": {"revision": "52b38439e5175ba6dc4c722c88fa43860638f559", "evidence": "runtime-version:3.13.7+git-tag:v3.13.7"},
    "valkey": {"revision": "a9245aaf3286dee1795763661f0da6886acd8ef4", "evidence": "runtime-version:8.1.9+git-tag:8.1.9"},
    "caddy": {"revision": "7088605cc11c52c2777ab613dfc5c2a9816006e4", "evidence": "git-tag:v2.8.4"},
    "grafana": {"revision": "c57667e4481563f5e6cf945b03bc0626caa4dbeb", "evidence": "git-tag:v11.2.0"},
    "prometheus": {"revision": "e6cfa720fbe6280153fab13090a483dbd40bece3", "evidence": "git-tag:v2.54.1"},
    "node-red": {"revision": "ff565bacb4a4d84326c2e27eafd0732c272abfcb", "evidence": "git-tag:4.0.9"},
    "litellm": {"revision": "418c7c6012d7c39a9d4a28c72cabe1995595ad2b", "evidence": "oci-label:org.opencontainers.image.revision"},
    "opentelemetry-collector": {"revision": "bef563ebb0f3a73fb8681d4ca4178ddf244042b6", "evidence": "oci-label:org.opencontainers.image.revision"},
    "openoutreach": {"revision": "ba6c25d94d8e644cf97d6e7df7e805106526c990", "evidence": "git-tag:v0.1.0"},
    "kimi-k3": {"revision": "a590ce090cb049c93a33dfe8c208ec652aa20503", "evidence": "huggingface-revision"},
    "deepseek": {"revision": "e815299b0bcbac849fa540c768ef21845365c9eb", "evidence": "huggingface-revision"},
}
COMPONENT_LICENSE_SOURCES = {
    "python-runtime": ("https://raw.githubusercontent.com/python/cpython/2abcf904b8dac8c999d2b3aac76681abb333798a/LICENSE", "3b2f81fe21d181c499c59a256c8e1968455d6689d269aa85373bfb6af41da3bf"),
    "postgresql": ("https://raw.githubusercontent.com/postgres/postgres/7d3e000c5961a544302072058a1184e9a588837b/COPYRIGHT", "3d6af92ff8a4c2cdf69afb1cf44edea727922f5cd0cf8b5f72b11cdecac8fdfd"),
    "rabbitmq": ("https://raw.githubusercontent.com/rabbitmq/rabbitmq-server/52b38439e5175ba6dc4c722c88fa43860638f559/LICENSE-MPL-RabbitMQ", "fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85"),
    "valkey": ("https://raw.githubusercontent.com/valkey-io/valkey/a9245aaf3286dee1795763661f0da6886acd8ef4/COPYING", "1a53dca3aab7ce048e91e77b03c0342f3075366f9dede8ec4d19d0cf229e12a0"),
    "keycloak-shadow-validation": ("https://raw.githubusercontent.com/keycloak/keycloak/289376b142480b4d600aca7acb1e4651862ed2a1/LICENSE.txt", "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"),
    "litellm": ("https://raw.githubusercontent.com/BerriAI/litellm/418c7c6012d7c39a9d4a28c72cabe1995595ad2b/LICENSE", "b170d6bf8e8835dd357e011681db028f4d51e2fb0ea892058f56e01fb39b8273"),
    "node-red": ("https://raw.githubusercontent.com/node-red/node-red/ff565bacb4a4d84326c2e27eafd0732c272abfcb/LICENSE", "876efc5b0ea06ac893b0d5f88bba8abfc050d82d157d65a95453abcb4dd6b0e0"),
    "prometheus": ("https://raw.githubusercontent.com/prometheus/prometheus/e6cfa720fbe6280153fab13090a483dbd40bece3/LICENSE", "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"),
    "grafana": ("https://raw.githubusercontent.com/grafana/grafana/c57667e4481563f5e6cf945b03bc0626caa4dbeb/LICENSE", "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0"),
    "opentelemetry-collector": ("https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector-releases/bef563ebb0f3a73fb8681d4ca4178ddf244042b6/LICENSE", "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"),
    "caddy": ("https://raw.githubusercontent.com/caddyserver/caddy/7088605cc11c52c2777ab613dfc5c2a9816006e4/LICENSE", "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"),
    "openoutreach": ("https://raw.githubusercontent.com/eracle/OpenOutreach/ba6c25d94d8e644cf97d6e7df7e805106526c990/LICENCE.md", "ccb349b4132ed7737f25e5adebfe61f3d52dca33708df1e50352320438d1d4c2"),
    "kimi-k3": ("https://huggingface.co/moonshotai/Kimi-K3/raw/a590ce090cb049c93a33dfe8c208ec652aa20503/LICENSE", "20c797ce19af0c17de52c6afb144644768a591c521655f5ebf5712c9850f2887"),
    "deepseek": ("https://huggingface.co/deepseek-ai/DeepSeek-V3/raw/e815299b0bcbac849fa540c768ef21845365c9eb/LICENSE-MODEL", "ccfee4895df06bcab524151c278e8dde88bbe76165a24ecbcbcf9fafd71fd2b3"),
}
MODEL_METADATA = {
    "kimi-k3": "moonshotai/Kimi-K3",
    "deepseek": "deepseek-ai/DeepSeek-V3",
}
OPENOUTREACH_RUNNER = ROOT / "tools" / "openoutreach_container_runner.py"
OPENOUTREACH_IMAGE = "ghcr.io/eracle/openoutreach@sha256:d6f355877c8f915057fe019a9f6b991a28e3752757c927de34280d9f56a9519b"
PACKAGE_LICENSE_SOURCES = {
    "langsmith": ("https://raw.githubusercontent.com/langchain-ai/langsmith-sdk/930be18058789110d7d9883d7b7d481f10fa1830/LICENSE", "34e0b9842c7a31d34e53bc7eb224e81e07a34996106e029bbc72dea2d449f496"),
}
SOURCE_ARCHIVES = {
    "openoutreach": {
        "url": "https://codeload.github.com/eracle/OpenOutreach/tar.gz/ba6c25d94d8e644cf97d6e7df7e805106526c990",
        "sha256": "0d394ec99dd9dcbbae7d2840d04fc84fbb2a896ab179f1418d52efa4b0582379",
        "filename": "openoutreach-ba6c25d94d8e644cf97d6e7df7e805106526c990.tar.gz",
    },
}


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()


def git_revision_timestamp() -> str:
    value = subprocess.run(
        ["git", "show", "-s", "--format=%cI", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    return datetime.fromisoformat(value).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def docker_image_digest(reference: str) -> str | None:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", reference],
        capture_output=True, text=True, check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and re.fullmatch(r"sha256:[0-9a-f]{64}", value) else None


def pinned_content(url: str, expected_sha256: str, existing: Path, fetch: bool) -> bytes | None:
    content: bytes | None = None
    if fetch:
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read()
    elif existing.is_file():
        content = existing.read_bytes()
    if content is not None and hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError(f"pinned content digest mismatch: {url}")
    return content


def image_scan_targets() -> dict[str, str]:
    targets = dict(THIRD_PARTY_IMAGES)
    targets.update({reference.split(":", 1)[0]: reference for reference in SERVICE_IMAGES})
    return targets


def add_image_license_blockers(manifest: dict[str, Any], blockers: list[dict[str, str]]) -> None:
    for scan_result in manifest.get("images", []):
        unknown = scan_result.get("unknown_license_packages", [])
        if unknown:
            blockers.append({
                "component": scan_result["name"],
                "field": "license_spdx",
                "reason": "image-sbom-license-curation-required",
                "count": len(unknown),
            })


def image_license_gap_report(manifest: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    total = 0
    for image in manifest.get("images", []):
        for raw in image.get("unknown_license_packages", []):
            total += 1
            item = raw if isinstance(raw, dict) else {"name": str(raw), "version": "", "purl": None}
            identity = str(item.get("purl") or item.get("name", "<unknown>"))
            version = str(item.get("version") or "")
            key = (identity, version)
            entry = grouped.setdefault(key, {
                "name": str(item.get("name", "<unknown>")),
                "version": version or None,
                "purl": item.get("purl"),
                "images": set(),
                "occurrences": 0,
            })
            entry["images"].add(image["name"])
            entry["occurrences"] += 1
    packages = []
    for entry in grouped.values():
        entry["images"] = sorted(entry["images"], key=str.casefold)
        packages.append(entry)
    packages.sort(key=lambda item: (item["name"].casefold(), item.get("version") or "", item.get("purl") or ""))
    return {
        "schema_version": 1,
        "total_unknown_license_declarations": total,
        "unique_package_versions": len(packages),
        "packages": packages,
    }


def unknown_license_packages(spdx: dict[str, Any]) -> list[dict[str, Any]]:
    unknown = []
    for package in spdx.get("packages", []):
        if package.get("licenseDeclared") not in {None, "", "NOASSERTION"}:
            continue
        purl = None
        for external in package.get("externalRefs", []) or []:
            if external.get("referenceType") == "purl":
                purl = external.get("referenceLocator")
                break
        unknown.append({
            "name": str(package.get("name", "<unknown>")),
            "version": package.get("versionInfo"),
            "purl": purl,
        })
    return sorted(
        unknown, key=lambda item: (item["name"].casefold(), str(item.get("version") or ""), str(item.get("purl") or "")),
    )


def refresh_image_manifest_findings(manifest: dict[str, Any]) -> None:
    for image in manifest.get("images", []):
        descriptor = image.get("spdx", {})
        path = OUT / str(descriptor.get("path", ""))
        if path.is_file():
            image["unknown_license_packages"] = unknown_license_packages(
                json.loads(path.read_text(encoding="utf-8")),
            )


def scan_image_sboms(syft: Path, blockers: list[dict[str, str]]) -> dict[str, Any]:
    version_result = subprocess.run([str(syft), "version", "-o", "json"], capture_output=True, text=True, check=False)
    if version_result.returncode != 0:
        raise RuntimeError(f"could not execute Syft: {version_result.stderr.strip()}")
    version_data = json.loads(version_result.stdout)
    scanner_version = str(version_data.get("version", "unknown"))
    targets = image_scan_targets()
    destination = OUT / "image-sboms"
    destination.mkdir(parents=True, exist_ok=True)

    def scan(name: str, reference: str) -> dict[str, Any]:
        image_id = docker_image_digest(reference)
        if image_id is None:
            raise RuntimeError(f"local image is unavailable: {reference}")
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", name)
        cdx_path = destination / f"{safe_name}.cdx.json"
        spdx_path = destination / f"{safe_name}.spdx.json"
        result = subprocess.run(
            [str(syft), "scan", f"docker:{image_id}",
             "-o", f"cyclonedx-json={cdx_path}", "-o", f"spdx-json={spdx_path}", "-q"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Syft failed for {reference}: {result.stderr.strip()}")
        cdx = json.loads(cdx_path.read_text(encoding="utf-8"))
        spdx = json.loads(spdx_path.read_text(encoding="utf-8"))
        unknown = unknown_license_packages(spdx)
        return {
            "name": name, "reference": reference, "image_id": image_id,
            "cyclonedx": {"path": cdx_path.relative_to(OUT).as_posix(), "sha256": hashlib.sha256(cdx_path.read_bytes()).hexdigest(),
                          "components": len(cdx.get("components", []))},
            "spdx": {"path": spdx_path.relative_to(OUT).as_posix(), "sha256": hashlib.sha256(spdx_path.read_bytes()).hexdigest(),
                     "packages": len(spdx.get("packages", []))},
            "unknown_license_packages": unknown,
        }

    scans = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(scan, name, reference): name for name, reference in targets.items()}
        for future in as_completed(futures):
            scans.append(future.result())
    scans.sort(key=lambda item: item["name"].casefold())
    manifest = {
        "scanner": {
            "name": "syft",
            "version": scanner_version,
            "sha256": hashlib.sha256(syft.read_bytes()).hexdigest(),
        },
        "images": scans,
    }
    add_image_license_blockers(manifest, blockers)
    return manifest


def runtime_packages() -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in RUNTIME_LOCK.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^ \\]+)", line)
        if match:
            current = {"name": match.group(1), "version": match.group(2), "hashes": []}
            packages.append(current)
        elif current:
            digest = re.search(r"--hash=sha256:([0-9a-f]{64})", line)
            if digest:
                current["hashes"].append(digest.group(1))
    return packages


def wheel_identity(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError(f"wheel must contain exactly one METADATA file: {path.name}")
        metadata = archive.read(metadata_names[0]).decode("utf-8", errors="replace")
    name_match = re.search(r"^Name:\s*(.+)$", metadata, re.MULTILINE | re.IGNORECASE)
    version_match = re.search(r"^Version:\s*(.+)$", metadata, re.MULTILINE | re.IGNORECASE)
    if not name_match or not version_match:
        raise ValueError(f"wheel identity is incomplete: {path.name}")
    name = name_match.group(1).strip().lower().replace("_", "-").replace(".", "-")
    return name, version_match.group(1).strip()


def select_wheels(packages: list[dict[str, Any]], fetch: bool) -> list[dict[str, Any]]:
    if fetch:
        with tempfile.TemporaryDirectory(prefix="atlantis-wheelhouse-") as temporary:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "download", "--require-hashes", "--only-binary=:all:",
                 "--dest", temporary, "-r", str(RUNTIME_LOCK)],
                cwd=ROOT, check=False, capture_output=True, text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"could not resolve locked wheels: {result.stderr.strip()}")
            WHEELHOUSE.mkdir(parents=True, exist_ok=True)
            for stale in WHEELHOUSE.glob("*.whl"):
                stale.unlink()
            for source in sorted(Path(temporary).glob("*.whl")):
                shutil.copyfile(source, WHEELHOUSE / source.name)

    selected: dict[str, tuple[Path, str, str]] = {}
    for wheel in sorted(WHEELHOUSE.glob("*.whl")) if WHEELHOUSE.is_dir() else []:
        name, version = wheel_identity(wheel)
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if name in selected:
            raise ValueError(f"multiple selected wheels for package: {name}")
        selected[name] = (wheel, version, digest)

    manifest = []
    for package in packages:
        normalized = package["name"].lower().replace("_", "-").replace(".", "-")
        match = selected.get(normalized)
        if match is None:
            continue
        wheel, version, digest = match
        if version != package["version"]:
            raise ValueError(f"selected wheel version mismatch for {package['name']}: {version}")
        if digest not in package["hashes"]:
            raise ValueError(f"selected wheel digest is absent from runtime lock: {wheel.name}")
        package["selected_wheel"] = wheel.name
        package["selected_digest"] = digest
        manifest.append({
            "name": package["name"], "version": version, "path": f"wheelhouse/{wheel.name}",
            "sha256": digest, "size": wheel.stat().st_size,
        })
    unexpected = sorted(set(selected) - {
        package["name"].lower().replace("_", "-").replace(".", "-") for package in packages
    })
    if unexpected:
        raise ValueError(f"wheelhouse contains unlocked packages: {', '.join(unexpected)}")
    return manifest


def installed_python_metadata() -> dict[str, dict[str, Any]]:
    extractor = r'''import base64, importlib.metadata as metadata, json
rows = {}
for distribution in metadata.distributions():
    name = distribution.metadata.get("Name")
    if not name:
        continue
    key = name.lower().replace("_", "-").replace(".", "-")
    files = []
    for relative in distribution.files or []:
        value = str(relative)
        basename = value.rsplit("/", 1)[-1].lower()
        if ".dist-info/" not in value or not basename.startswith(("license", "copying", "notice")):
            continue
        target = distribution.locate_file(relative)
        try:
            content = target.read_bytes()
        except OSError:
            continue
        files.append({"path": value, "content_base64": base64.b64encode(content).decode("ascii")})
    rows[key] = {
        "name": name,
        "version": distribution.version,
        "declared_license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License"),
        "license_files": sorted(files, key=lambda item: item["path"]),
    }
print(json.dumps(rows, sort_keys=True))'''
    result = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "python", PYTHON_BASE_IMAGE, "-c", extractor],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return {}
    data = json.loads(result.stdout)
    return data if isinstance(data, dict) else {}


def materialize_python_licenses(
    packages: list[dict[str, Any]], metadata: dict[str, dict[str, Any]], fetch_pinned: bool,
) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    root = OUT / "LICENSES" / "python"
    root.mkdir(parents=True, exist_ok=True)
    for package in packages:
        normalized = package["name"].lower().replace("_", "-").replace(".", "-")
        installed = metadata.get(normalized, {})
        package["declared_license"] = installed.get("declared_license")
        files = []
        combined_parts = []
        license_files = list(installed.get("license_files", []))
        pinned = PACKAGE_LICENSE_SOURCES.get(normalized)
        pinned_target = root / normalized / "01-LICENSE"
        if not license_files and pinned:
            content = pinned_content(pinned[0], pinned[1], pinned_target, fetch_pinned)
            if content is not None:
                license_files.append({"path": f"pinned-source:{pinned[0]}", "content_base64": base64.b64encode(content).decode("ascii")})
        for index, item in enumerate(license_files, start=1):
            content = base64.b64decode(item["content_base64"])
            basename = re.sub(r"[^A-Za-z0-9_.-]", "_", item["path"].rsplit("/", 1)[-1])
            relative = Path("LICENSES") / "python" / normalized / f"{index:02d}-{basename}"
            target = OUT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            files.append({"path": relative.as_posix(), "sha256": hashlib.sha256(content).hexdigest()})
            combined_parts.append(f"===== {item['path']} =====\n".encode("utf-8") + content.rstrip() + b"\n")
        combined_path = None
        combined_sha256 = None
        if combined_parts:
            combined = b"\n".join(combined_parts)
            combined_relative = Path("LICENSES") / "python" / normalized / "COMPLETE_LICENSE_TEXTS.txt"
            (OUT / combined_relative).write_bytes(combined)
            combined_path = combined_relative.as_posix()
            combined_sha256 = hashlib.sha256(combined).hexdigest()
        package["license_path"] = combined_path or "TBD"
        package["license_text_sha256"] = combined_sha256 or "TBD"
        inventory.append({
            "name": package["name"], "version": package["version"],
            "declared_license": package["declared_license"], "files": files,
            "combined_license_path": combined_path, "combined_license_sha256": combined_sha256,
        })
    return inventory


def materialize_component_licenses(components: list[dict[str, Any]], fetch_pinned: bool) -> None:
    root = OUT / "LICENSES" / "components"
    root.mkdir(parents=True, exist_ok=True)
    for component in components:
        source = COMPONENT_LICENSE_SOURCES.get(component["name"])
        if source is None:
            continue
        target = root / f"{component['name']}.txt"
        content = pinned_content(source[0], source[1], target, fetch_pinned)
        if content is None:
            continue
        target.write_bytes(content)
        component["license_path"] = target.relative_to(OUT).as_posix()
        component["license_text_sha256"] = source[1]
        component["license_source"] = source[0]


def materialize_corresponding_sources(components: list[dict[str, Any]], fetch_pinned: bool) -> None:
    root = OUT / "corresponding-source"
    root.mkdir(parents=True, exist_ok=True)
    for component in components:
        source = SOURCE_ARCHIVES.get(component["name"])
        if source is None:
            continue
        component_root = root / component["name"]
        target = component_root / source["filename"]
        content = pinned_content(source["url"], source["sha256"], target, fetch_pinned)
        if content is None:
            continue
        component_root.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        component["artifact"] = target.relative_to(OUT).as_posix()
        component["digest"] = f"sha256:{source['sha256']}"
        component["source_path"] = target.relative_to(root).as_posix()
        component["source_sha256"] = source["sha256"]


def materialize_model_descriptors(components: list[dict[str, Any]], fetch: bool) -> None:
    root = OUT / "model-descriptors"
    root.mkdir(parents=True, exist_ok=True)
    for component in components:
        model_id = MODEL_METADATA.get(component["name"])
        if model_id is None:
            continue
        revision = component["revision"]
        target = root / f"{component['name']}.json"
        if fetch:
            url = f"https://huggingface.co/api/models/{model_id}/revision/{revision}?blobs=true"
            with urllib.request.urlopen(url, timeout=30) as response:
                remote = json.load(response)
            if remote.get("sha") != revision:
                raise ValueError(f"model repository revision mismatch: {model_id}")
            descriptor = {
                "schema_version": 1,
                "provider": "huggingface",
                "model_id": model_id,
                "revision": revision,
                "files": sorted(({
                    key: sibling[key] for key in ("rfilename", "blobId", "size", "lfs") if key in sibling
                } for sibling in remote.get("siblings", [])), key=lambda item: item["rfilename"]),
            }
            target.write_text(canonical_json(descriptor) + "\n", encoding="utf-8")
        if target.is_file():
            descriptor = json.loads(target.read_text(encoding="utf-8"))
            if descriptor.get("model_id") != model_id or descriptor.get("revision") != revision:
                raise ValueError(f"cached model descriptor mismatch: {model_id}")
            component["artifact"] = target.relative_to(OUT).as_posix()
            component["digest"] = f"sha256:{hashlib.sha256(target.read_bytes()).hexdigest()}"


def normalized_components(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    source = yaml.safe_load(SPEC_LOCK.read_text(encoding="utf-8"))
    components: list[dict[str, str]] = []
    for item in source.get("components", []):
        revision = str(item.get("commit") or item.get("tag_or_revision") or "TBD")
        component = {
            "name": str(item.get("name", "TBD")),
            "kind": str(item.get("kind", "TBD")),
            "repository": str(item.get("repository", "TBD")),
            "revision": revision,
            "artifact": str(item.get("artifact_or_model_id", "TBD")),
            "digest": str(item.get("digest", "TBD")),
            "license_spdx": str(item.get("license_spdx", "TBD")),
            "license_text_sha256": str(item.get("license_text_sha256", "TBD")),
            "license_path": "TBD",
            "owner": str(item.get("owner", "TBD")),
            "distribution_mode": str(item.get("distribution_mode", "TBD")),
            "source_obligation": str(item.get("source_obligation", "TBD")),
        }
        pin = PINNED_SOURCE_REVISIONS.get(component["name"])
        if pin:
            component["revision"] = pin["revision"]
            component["revision_evidence"] = pin["evidence"]
        components.append(component)
    revision = git_revision()
    for reference in SERVICE_IMAGES:
        digest = docker_image_digest(reference)
        name = reference.split(":", 1)[0]
        components.append({
            "name": name,
            "kind": "oci-image",
            "repository": f"local-docker://{name}",
            "revision": revision,
            "artifact": reference,
            "digest": digest or "TBD",
            "license_spdx": "LicenseRef-Proprietary-Atlantis",
            "license_text_sha256": hashlib.sha256((ROOT / "LICENSE").read_bytes()).hexdigest(),
            "license_path": "LICENSES/Atlantis-Proprietary.txt",
            "owner": "Platform",
            "distribution_mode": "proprietary-service-image",
            "source_obligation": "proprietary-license-notice",
        })
        blockers.append({
            "component": name,
            "field": "repository",
            "reason": "local-image-id-must-be-replaced-by-published-registry-manifest-digest",
        })
        if digest is None:
            blockers.append({"component": name, "field": "digest", "reason": "local-image-missing"})
    return components


def cyclonedx_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in components:
        license_value = item["license_spdx"]
        license_choice = ({"license": {"id": license_value}}
                          if re.fullmatch(r"[A-Za-z0-9.+-]+", license_value)
                          else {"expression": license_value})
        component: dict[str, Any] = {
            "type": "container" if item["kind"] == "oci-image" else "library",
            "name": item["name"],
            "version": item["revision"],
            "licenses": [license_choice],
            "properties": [
                {"name": "atlantis:repository", "value": item["repository"]},
                {"name": "atlantis:artifact", "value": item["artifact"]},
            ],
        }
        if re.fullmatch(r"sha256:[0-9a-f]{64}", item["digest"]):
            component["hashes"] = [{"alg": "SHA-256", "content": item["digest"].removeprefix("sha256:")}]
        elif item.get("all_hashes"):
            component["hashes"] = [{"alg": "SHA-256", "content": digest} for digest in item["all_hashes"]]
        if item.get("purl"):
            component["purl"] = item["purl"]
        result.append(component)
    return result


def spdx_id(name: str) -> str:
    return "SPDXRef-Package-" + re.sub(r"[^A-Za-z0-9.-]", "-", name)


def spdx_document(components: list[dict[str, Any]]) -> dict[str, Any]:
    packages = []
    relationships = []
    for item in components:
        package: dict[str, Any] = {
            "SPDXID": spdx_id(item["name"]),
            "name": item["name"],
            "versionInfo": item["revision"],
            "downloadLocation": item["repository"] if item["repository"].startswith(("http://", "https://")) else "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": item["license_spdx"],
            "copyrightText": "NOASSERTION",
        }
        if re.fullmatch(r"sha256:[0-9a-f]{64}", item["digest"]):
            package["checksums"] = [{"algorithm": "SHA256", "checksumValue": item["digest"].removeprefix("sha256:")}]
        if item.get("purl"):
            package["externalRefs"] = [{
                "referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl", "referenceLocator": item["purl"],
            }]
        packages.append(package)
        relationships.append({
            "spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": package["SPDXID"],
        })
    namespace_seed = hashlib.sha256(canonical_json(packages).encode("utf-8")).hexdigest()
    return {
        "spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT",
        "name": "atlantis-autonomous-sales-0.9.0-rc5-candidate",
        "documentNamespace": f"https://atlantis.invalid/spdx/{namespace_seed}",
        "creationInfo": {"created": git_revision_timestamp(), "creators": ["Tool: Atlantis distribution candidate generator"]},
        "packages": packages, "relationships": relationships,
    }


def notices_document(components: list[dict[str, Any]]) -> str:
    lines = [
        "# Third-party notices — distribution candidate", "",
        "> BLOCKED: generated inventory for review; this is not a Legal approval or release authorization.", "",
    ]
    for item in sorted(components, key=lambda component: component["name"].casefold()):
        lines.extend([
            f"## {item['name']}", "",
            f"- Revision: `{item['revision']}`",
            f"- License declaration: `{item['license_spdx']}`",
            f"- Repository/source: {item['repository']}",
            f"- Distribution mode: `{item['distribution_mode']}`",
            f"- Source obligation: {item['source_obligation']}", "",
        ])
    return "\n".join(lines)


def source_manifest(components: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for item in sorted(components, key=lambda component: component["name"].casefold()):
        obligation = item["source_obligation"].casefold()
        requires_source = any(marker in obligation for marker in ("include", "source-offer", "corresponding-source"))
        included = bool(item.get("source_path"))
        entries.append({
            "name": item["name"],
            "disposition": "included" if included else ("pending-review" if requires_source else "not-required-candidate"),
            "obligation": item["source_obligation"],
            "path": item.get("source_path"),
            "sha256": item.get("source_sha256"),
        })
    return {"schema_version": 1, "release_status": "blocked", "components": entries}


def legal_review_queue(
    components: list[dict[str, Any]], license_inventory: list[dict[str, Any]], image_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build one deterministic, explicitly non-authoritative queue for Legal review."""
    component_reviews = [{
        "name": item["name"],
        "revision": item["revision"],
        "license_spdx": item["license_spdx"],
        "license_path": item["license_path"],
        "license_text_sha256": item["license_text_sha256"],
        "source_obligation": item["source_obligation"],
    } for item in sorted(components, key=lambda component: component["name"].casefold())]
    python_reviews = [{
        "name": item["name"],
        "version": item["version"],
        "declared_license": item.get("declared_license"),
        "license_path": item.get("license_path"),
        "license_text_sha256": item.get("license_text_sha256"),
    } for item in sorted(license_inventory, key=lambda package: package["name"].casefold())]
    image_gaps = image_license_gap_report(image_manifest) if image_manifest is not None else {
        "total_unknown_license_declarations": 0, "unique_package_versions": 0, "packages": [],
    }
    return {
        "schema_version": 1,
        "release_status": "blocked",
        "legal_approval_recorded": False,
        "component_declarations": component_reviews,
        "python_package_declarations": python_reviews,
        "image_license_gaps": image_gaps,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-wheels", action="store_true", help="download the exact hash-locked CPython wheels")
    parser.add_argument("--scan-images", action="store_true", help="generate package-level SBOMs for every local OCI image")
    parser.add_argument("--syft", type=Path, default=Path("syft"), help="path to the Syft executable")
    parser.add_argument("--fetch-licenses", action="store_true", help="fetch license texts pinned by URL and SHA-256")
    parser.add_argument("--fetch-sources", action="store_true", help="fetch corresponding-source archives pinned by SHA-256")
    parser.add_argument("--fetch-model-metadata", action="store_true", help="fetch pinned model repository descriptors without downloading weights")
    args = parser.parse_args()
    blockers: list[dict[str, str]] = []
    components = normalized_components(blockers)
    packages = runtime_packages()
    wheel_manifest = select_wheels(packages, args.fetch_wheels)
    image_manifest_path = OUT / "image-sboms" / "manifest.candidate.json"
    image_manifest = scan_image_sboms(args.syft, blockers) if args.scan_images else None
    if image_manifest is None and image_manifest_path.is_file():
        existing_image_manifest = json.loads(image_manifest_path.read_text(encoding="utf-8"))
        refresh_image_manifest_findings(existing_image_manifest)
        image_manifest = existing_image_manifest
        add_image_license_blockers(image_manifest, blockers)
    metadata = installed_python_metadata()
    license_inventory = materialize_python_licenses(packages, metadata, args.fetch_licenses)
    (OUT / "LICENSES" / "Atlantis-Proprietary.txt").write_bytes((ROOT / "LICENSE").read_bytes())
    materialize_component_licenses(components, args.fetch_licenses)
    materialize_corresponding_sources(components, args.fetch_sources)
    materialize_model_descriptors(components, args.fetch_model_metadata)
    runner = Path("/opt/atlantis/opensource/openoutreach-runner/runner.sh")
    if runner.is_file():
        runner_text = runner.read_text(encoding="utf-8", errors="replace")
        if "leads de ejemplo" in runner_text or "example.org/dir/" in runner_text:
            blockers.append({"component": "openoutreach", "field": "runtime", "reason": "installed-runtime-is-fixture"})
        elif runner.read_bytes() != OPENOUTREACH_RUNNER.read_bytes():
            blockers.append({"component": "openoutreach", "field": "runtime", "reason": "installed-runtime-digest-not-bound-to-candidate"})
        else:
            openoutreach = next(item for item in components if item["name"] == "openoutreach")
            openoutreach["runtime_wrapper_sha256"] = hashlib.sha256(runner.read_bytes()).hexdigest()
            openoutreach["runtime_image"] = OPENOUTREACH_IMAGE
    else:
        blockers.append({"component": "openoutreach", "field": "runtime", "reason": "external-runtime-not-installed"})
    component_by_name = {item["name"].casefold(): item for item in components}
    for package in packages:
        reason = "verify-installed-package-declaration" if package.get("declared_license") else "installed-package-license-metadata-missing"
        blockers.append({"component": package["name"], "field": "license_spdx", "reason": reason})
        if not package.get("selected_digest"):
            blockers.append({"component": package["name"], "field": "digest", "reason": "select-exact-distributed-wheel"})
        package_component = {
            "name": package["name"],
            "kind": "python-package",
            "repository": f"https://pypi.org/project/{package['name']}/",
            "revision": package["version"],
            "artifact": (f"wheelhouse/{package['selected_wheel']}" if package.get("selected_wheel")
                         else f"pkg:pypi/{package['name']}@{package['version']}"),
            "purl": f"pkg:pypi/{package['name']}@{package['version']}",
            "digest": f"sha256:{package['selected_digest']}" if package.get("selected_digest") else "TBD",
            "all_hashes": package["hashes"],
            "license_spdx": package.get("declared_license") or "TBD",
            "license_text_sha256": package["license_text_sha256"],
            "license_path": package["license_path"],
            "owner": "Platform",
            "distribution_mode": "proprietary-service-runtime-dependency",
            "source_obligation": "pending-legal-verification",
        }
        existing = component_by_name.get(package["name"].casefold())
        if existing is None:
            components.append(package_component)
            component_by_name[package["name"].casefold()] = package_component
        else:
            existing.update({
                "revision": package["version"],
                "artifact": package_component["artifact"],
                "purl": package_component["purl"],
                "digest": package_component["digest"],
                "all_hashes": package["hashes"],
                "license_text_sha256": package["license_text_sha256"],
                "license_path": package["license_path"],
            })
    for component in components:
        for field in (
            "repository", "revision", "artifact", "digest", "license_spdx", "license_text_sha256",
            "license_path", "owner", "distribution_mode", "source_obligation",
        ):
            if str(component.get(field, "")).strip().upper() in PENDING:
                blockers.append({"component": component["name"], "field": field, "reason": "not-fixed"})
    lock = {
        "schema_version": 1,
        "release_status": "blocked",
        "source_revision": git_revision(),
        "components": components,
    }
    sbom_components = cyclonedx_components(components)
    serial_seed = hashlib.sha256(canonical_json(sbom_components).encode("utf-8")).hexdigest()
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{serial_seed[:8]}-{serial_seed[8:12]}-{serial_seed[12:16]}-{serial_seed[16:20]}-{serial_seed[20:32]}",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": "atlantis-autonomous-sales", "version": "0.9.0-rc5"}},
        "components": sbom_components,
        "properties": [{"name": "atlantis:distribution-status", "value": "blocked-candidate-only"}],
    }
    report = {
        "schema_version": 1,
        "distribution_authorized": False,
        "blocker_count": len(blockers),
        "blockers": sorted(blockers, key=lambda item: (item["component"], item["field"], item["reason"])),
        "required_human_approvals": ["release", "security", "legal"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "component-lock.candidate.json").write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "sbom.cdx.candidate.json").write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "sbom.spdx.candidate.json").write_text(
        json.dumps(spdx_document(components), indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    (OUT / "THIRD_PARTY_NOTICES.candidate.md").write_text(notices_document(components), encoding="utf-8")
    source_root = OUT / "corresponding-source"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "manifest.candidate.json").write_text(
        json.dumps(source_manifest(components), indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    (OUT / "wheelhouse-manifest.candidate.json").write_text(
        json.dumps({"runtime_lock": str(RUNTIME_LOCK.relative_to(ROOT)), "artifacts": wheel_manifest}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if image_manifest is not None:
        image_manifest_path.write_text(json.dumps(image_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (OUT / "IMAGE_LICENSE_GAPS.json").write_text(
            json.dumps(image_license_gap_report(image_manifest), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (OUT / "BLOCKERS.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "license-inventory.candidate.json").write_text(
        json.dumps({"source_image": PYTHON_BASE_IMAGE, "packages": license_inventory}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "LEGAL_REVIEW_QUEUE.json").write_text(
        json.dumps(legal_review_queue(components, license_inventory, image_manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "BLOCKED_CANDIDATE_GENERATED", "components": len(sbom_components), "blockers": len(blockers)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
