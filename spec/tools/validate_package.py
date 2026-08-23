#!/usr/bin/env python3
"""Dependency-light structural validator for the Atlantis OpenSpec package."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CHANGE = ROOT / "openspec" / "changes" / "integrate-autonomous-sales-platform"
errors: list[str] = []
warnings: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def resolve_ref(doc: dict, ref: str):
    if not ref.startswith("#/"):
        fail(f"OpenAPI reference is not local: {ref}")
        return None
    value = doc
    for part in ref[2:].split("/"):
        if not isinstance(value, dict) or part not in value:
            fail(f"Broken OpenAPI reference: {ref}")
            return None
        value = value[part]
    return value


required = [
    ROOT / "README.md",
    ROOT / "SOURCES.md",
    ROOT / "contracts" / "openapi.yaml",
    ROOT / "database" / "schema.sql",
    ROOT / "database" / "002_hardening_v1_1.sql",
    ROOT / "compliance" / "component-lock.yaml",
    ROOT / "compliance" / "DISTRIBUTION_GATE.md",
    CHANGE / "proposal.md",
    CHANGE / "design.md",
    CHANGE / "tasks.md",
]
for path in required:
    if not path.is_file():
        fail(f"Missing required file: {path.relative_to(ROOT)}")

config = yaml.safe_load((ROOT / "openspec" / "config.yaml").read_text(encoding="utf-8"))
if config.get("schema") != "spec-driven":
    fail("openspec/config.yaml must declare schema: spec-driven")

spec_files = sorted((CHANGE / "specs").glob("*/spec.md"))
if not spec_files:
    fail("No capability specs found")

for path in spec_files:
    text = path.read_text(encoding="utf-8")
    if "## ADDED Requirements" not in text:
        fail(f"{path.relative_to(ROOT)} lacks ## ADDED Requirements")
    reqs = list(re.finditer(r"(?m)^### Requirement: (.+)$", text))
    if not reqs:
        fail(f"{path.relative_to(ROOT)} has no requirements")
        continue
    for i, match in enumerate(reqs):
        end = reqs[i + 1].start() if i + 1 < len(reqs) else len(text)
        block = text[match.end():end]
        name = match.group(1)
        if not re.search(r"\b(?:SHALL|MUST|MAY|SHALL NOT|MUST NOT)\b", block):
            fail(f"{path.relative_to(ROOT)} requirement '{name}' lacks normative language")
        scenarios = re.split(r"(?m)^#### Scenario: .+$", block)[1:]
        if not scenarios:
            fail(f"{path.relative_to(ROOT)} requirement '{name}' lacks scenarios")
        for number, scenario in enumerate(scenarios, start=1):
            for keyword in ("GIVEN", "WHEN", "THEN"):
                if f"**{keyword}**" not in scenario:
                    fail(f"{path.relative_to(ROOT)} requirement '{name}' scenario {number} lacks {keyword}")

lock = yaml.safe_load((ROOT / "compliance" / "component-lock.yaml").read_text(encoding="utf-8"))
required_component_fields = {
    "name", "kind", "repository", "tag_or_revision", "commit",
    "artifact_or_model_id", "digest", "license_spdx", "license_text_sha256",
    "owner", "distribution_mode", "source_obligation",
}
for component in lock.get("components", []):
    missing = required_component_fields - set(component)
    if missing:
        fail(f"component-lock entry {component.get('name', '<unknown>')} lacks {sorted(missing)}")
serialized_lock = yaml.safe_dump(lock, sort_keys=True)
if "TBD" in serialized_lock or "UNKNOWN" in serialized_lock:
    if lock.get("release_status") != "blocked":
        fail("component-lock with pending values must declare release_status: blocked")
    warn("component-lock contains pending values; package is valid for design but blocked for release")
if "n8n" not in lock.get("policy", {}).get("forbidden_components", []):
    fail("component-lock policy must forbid n8n")

api = yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8"))
if api.get("openapi") != "3.1.0":
    fail("OpenAPI contract must use 3.1.0")

operation_ids: set[str] = set()
for route, path_item in api.get("paths", {}).items():
    route_params = set(re.findall(r"{([^}]+)}", route))
    for method, operation in path_item.items():
        if method not in {"get", "post", "put", "patch", "delete", "options", "head", "trace"}:
            continue
        operation_id = operation.get("operationId")
        if not operation_id:
            fail(f"{method.upper()} {route} lacks operationId")
        elif operation_id in operation_ids:
            fail(f"Duplicate operationId: {operation_id}")
        else:
            operation_ids.add(operation_id)
        if not operation.get("responses"):
            fail(f"{method.upper()} {route} lacks responses")
        declared = set()
        for param in operation.get("parameters", []):
            resolved = resolve_ref(api, param["$ref"]) if "$ref" in param else param
            if resolved and resolved.get("in") == "path":
                declared.add(resolved.get("name"))
        if route_params != declared:
            fail(f"{method.upper()} {route} path parameters differ: route={route_params}, declared={declared}")

def walk(value):
    if isinstance(value, dict):
        if "$ref" in value:
            resolve_ref(api, value["$ref"])
        for child in value.values():
            walk(child)
    elif isinstance(value, list):
        for child in value:
            walk(child)

walk(api)

declared_scopes: dict[str, set[str]] = {}
for scheme, body in api.get("components", {}).get("securitySchemes", {}).items():
    scopes = set()
    for flow in body.get("flows", {}).values():
        scopes.update(flow.get("scopes", {}).keys())
    declared_scopes[scheme] = scopes

for security in [api.get("security", [])] + [
    op.get("security", [])
    for path_item in api.get("paths", {}).values()
    for method, op in path_item.items()
    if method in {"get", "post", "put", "patch", "delete"}
]:
    for item in security:
        for scheme, scopes in item.items():
            if scheme not in declared_scopes:
                fail(f"Unknown security scheme: {scheme}")
            for scope in scopes:
                if scope not in declared_scopes.get(scheme, set()):
                    fail(f"Unknown scope {scheme}:{scope}")

sql = "\n".join(
    path.read_text(encoding="utf-8")
    for path in [ROOT / "database" / "schema.sql", ROOT / "database" / "002_hardening_v1_1.sql"]
)
for token in [
    "CREATE TABLE action_intent",
    "CREATE TABLE repep_snapshot",
    "CREATE TABLE human_action",
    "CREATE TABLE policy_rule_set",
    "FORCE ROW LEVEL SECURITY",
    "prevent_audit_mutation",
    "workflow_version",
]:
    if token not in sql:
        fail(f"Database contract lacks required control: {token}")

if "control.internal.example" in (ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8"):
    warn("OpenAPI server and identity URLs are placeholders and must be replaced per environment")

for warning in warnings:
    print(f"WARN: {warning}")
for error in errors:
    print(f"ERROR: {error}")
print(f"Checked {len(spec_files)} capability specs and {len(operation_ids)} API operations")
if errors:
    print(f"FAILED with {len(errors)} error(s) and {len(warnings)} warning(s)")
    sys.exit(1)
print(f"PASS with {len(warnings)} warning(s)")
