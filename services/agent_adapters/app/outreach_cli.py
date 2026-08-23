import hashlib
import json
import os
import subprocess


class OpenOutreachRunner:
    """GPL boundary: invokes an unmodified executable and exchanges JSON only."""

    def __init__(self, executable: str, approved_sha256: str):
        self.executable = os.path.realpath(executable)
        self.approved_sha256 = approved_sha256

    def run(self, query: dict, timeout=120) -> list[dict]:
        if not os.path.isabs(self.executable) or not self.approved_sha256:
            raise RuntimeError("OPENOUTREACH_BINARY_NOT_PINNED")
        digest = hashlib.sha256()
        with open(self.executable, "rb") as binary:
            for chunk in iter(lambda: binary.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != self.approved_sha256:
            raise RuntimeError("OPENOUTREACH_BINARY_DIGEST_MISMATCH")
        result = subprocess.run(
            [self.executable, "--format", "jsonl"], input=json.dumps(query), text=True,
            capture_output=True, timeout=timeout, check=False, shell=False,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
        if result.returncode:
            raise RuntimeError("OPENOUTREACH_EXTERNAL_PROCESS_FAILED")
        leads = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        for lead in leads:
            if not all(key in lead for key in ("source_uri", "observed_at", "confidence")):
                raise ValueError("LEAD_PROVENANCE_REQUIRED")
        return leads
