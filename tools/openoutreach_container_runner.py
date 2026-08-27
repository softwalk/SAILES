#!/usr/bin/env python3
"""JSONL boundary adapter for the pinned, external GPL OpenOutreach container."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

IMAGE = "ghcr.io/eracle/openoutreach@sha256:d6f355877c8f915057fe019a9f6b991a28e3752757c927de34280d9f56a9519b"
DEFAULT_DATA = Path("/opt/atlantis/opensource/openoutreach-data")
DEFAULT_ENV = Path("/opt/atlantis/secrets/openoutreach.env")


def positive_count(query: dict[str, Any]) -> int:
    value = query.get("count", query.get("limit", 1))
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise ValueError("query count must be an integer between 1 and 100")
    return value


def transform(record: dict[str, Any]) -> dict[str, Any]:
    source = record.get("linkedin_url") or record.get("website")
    observed = record.get("qualified_at")
    if not source or not observed:
        raise ValueError("OpenOutreach record lacks source provenance")
    return {
        "source_uri": source,
        "observed_at": observed,
        "confidence": 1.0,
        "display_name": " ".join(filter(None, (record.get("first_name"), record.get("last_name")))),
        "company_name": record.get("company"),
        "title": record.get("title"),
        "website": record.get("website"),
        "email": record.get("email"),
        "reason": record.get("reason"),
        "upstream_lead_id": record.get("lead_id"),
    }


def run(query: dict[str, Any], data_dir: Path, env_file: Path) -> list[dict[str, Any]]:
    if not env_file.is_file():
        raise RuntimeError(f"missing OpenOutreach environment file: {env_file}")
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    command = [
        "docker", "run", "--rm", "--pull=never",
        "--env-file", str(env_file),
        "-v", f"{data_dir}:/app/data",
        IMAGE, "openoutreach", "find", str(positive_count(query)), "--new", "--json",
    ]
    campaign = query.get("campaign")
    if campaign:
        command.extend(["--campaign", str(campaign)])
    result = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False)
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown error"
        raise RuntimeError(f"OpenOutreach failed: {detail}")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict) or not isinstance(payload.get("leads"), list):
        raise RuntimeError("OpenOutreach returned an invalid JSON contract")
    return [transform(item) for item in payload["leads"]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["jsonl"], required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    args = parser.parse_args()
    try:
        query = json.load(sys.stdin)
        if not isinstance(query, dict):
            raise ValueError("query must be a JSON object")
        for lead in run(query, args.data_dir, args.env_file):
            print(json.dumps(lead, ensure_ascii=False, separators=(",", ":")))
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"OPENOUTREACH_EXTERNAL_PROCESS_FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

