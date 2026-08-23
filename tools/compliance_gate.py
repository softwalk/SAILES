#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".toml", ".yaml", ".yml", ".json", ".md", ".txt"}


def scan_source():
    errors = []
    for path in ROOT.rglob("*"):
        ignored = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}
        if (not path.is_file() or path.suffix not in TEXT_SUFFIXES
                or "evidence" in path.parts or ignored.intersection(path.parts)):
            continue
        text = path.read_text(errors="replace")
        relative = path.relative_to(ROOT)
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
    expected_dockerfiles = ["policy_gateway", "crm_api", "orchestrator", "model_gateway", "channel_adapters"]
    for service in expected_dockerfiles:
        if not (ROOT / "services" / service / "Dockerfile").exists():
            errors.append(f"Missing isolated build: services/{service}/Dockerfile")
    return errors


def distribution_errors():
    required = [
        ROOT / "release/evidence/sbom.cdx.json", ROOT / "release/evidence/THIRD_PARTY_NOTICES.md",
        ROOT / "release/evidence/LICENSES", ROOT / "release/evidence/corresponding-source",
        ROOT / "release/evidence/attestation.json", ROOT / "release/evidence/component-lock.json",
    ]
    errors = [f"Missing distribution artifact: {p.relative_to(ROOT)}" for p in required if not p.exists()]
    lock = ROOT / "release/evidence/component-lock.json"
    if lock.exists():
        data = json.loads(lock.read_text())
        for item in data.get("components", []):
            if any(str(item.get(key, "")).upper() in {"", "TBD", "UNSET", "UNKNOWN"} for key in ("repository", "revision", "digest", "license_spdx")):
                errors.append(f"Unpinned component: {item.get('name', '?')}")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["source", "distribution"], default="source")
    args = parser.parse_args()
    errors = scan_source()
    if args.mode == "distribution":
        errors += distribution_errors()
    if errors:
        print("COMPLIANCE GATE: BLOCKED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"COMPLIANCE GATE: PASS ({args.mode})")
    return 0


if __name__ == "__main__": sys.exit(main())
