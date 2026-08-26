#!/usr/bin/env python3
"""Authenticated live probes used by the VM pilot-readiness operation.

It never prints workload/JIT secrets or authorization tokens.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
from atlantis_contracts import AuthorizationClaims  # noqa: E402
from atlantis_contracts.security import sign_workload_request  # noqa: E402
from atlantis_contracts.token import sign_claims  # noqa: E402


def atomic_json(path: Path, value: dict):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


class Client:
    def __init__(self, secret_file: str, service_id="orchestrator"):
        secrets = json.loads(Path(secret_file).read_text(encoding="utf-8"))
        secret = secrets.get(service_id, "").encode()
        if len(secret) < 32:
            raise RuntimeError("PROBE_WORKLOAD_SECRET_MISSING")
        self.service_id, self.secret = service_id, secret

    def post(self, port: int, path: str, body: dict, *, expect: int) -> dict:
        payload = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
        timestamp, nonce = int(time.time()), str(uuid4())
        signature = sign_workload_request(self.secret, timestamp, nonce, "POST", path, payload)
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}", payload,
            {"Content-Type": "application/json", "X-Atlantis-Service": self.service_id,
             "X-Atlantis-Timestamp": str(timestamp), "X-Atlantis-Nonce": nonce,
             "X-Atlantis-Signature": signature, "Idempotency-Key": str(uuid4())},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                status, result = response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            status = exc.code
            result = json.loads(exc.read() or b"{}")
        if status != expect:
            raise RuntimeError(f"HTTP_EXPECTED_{expect}_GOT_{status}:{result.get('error','UNKNOWN')}")
        return result


def workflow_before(args):
    client = Client(args.workload_secrets)
    state = client.post(8083, "/v1/runs", {
        "tenant_id": args.tenant, "campaign_version_id": args.campaign_version,
        "contact_id": args.contact,
    }, expect=201)
    state = client.post(8083, "/v1/runs/transition", {
        "tenant_id": args.tenant, "run_id": state["run_id"], "event_id": str(uuid4()),
    }, expect=200)
    if state["stage"] != "PREPARE":
        raise RuntimeError("WORKFLOW_PRE_RESTART_STAGE_INVALID")
    atomic_json(Path(args.context), {"tenant_id": args.tenant, "run_id": state["run_id"]})
    print(f"PASS workflow pre-restart run_id={state['run_id']} stage=PREPARE")


def workflow_after(args):
    context = json.loads(Path(args.context).read_text(encoding="utf-8"))
    client = Client(args.workload_secrets)
    state = client.post(8083, "/v1/runs/transition", {
        "tenant_id": context["tenant_id"], "run_id": context["run_id"], "event_id": str(uuid4()),
    }, expect=200)
    if state["stage"] != "APPROVE" or state["status"] != "RUNNING":
        raise RuntimeError("WORKFLOW_POST_RESTART_STATE_INVALID")
    print(f"PASS workflow restored run_id={state['run_id']} stage=APPROVE")


def make_token(args):
    columns = Path(args.decision).read_text(encoding="utf-8").strip().split("\t")
    if len(columns) != 7:
        raise RuntimeError("DECISION_EVIDENCE_INVALID")
    tenant, contact, campaign, decision, channel, purpose, content_hash = columns
    now, jti = int(time.time()), str(uuid4())
    claims = AuthorizationClaims(
        jti=jti, iss="atlantis-policy-gateway", aud="voice-adapter", tenant_id=tenant,
        contact_id=contact, campaign_version_id=campaign, decision_id=decision,
        channel=channel, purpose=purpose, content_hash=content_hash, iat=now, exp=now + 120,
    )
    secret = Path(args.jit_secret).read_bytes().strip()
    token = sign_claims(secret, claims)
    value = {
        **claims.__dict__, "token": token,
        "nonce_hash": hashlib.sha256(jti.encode()).hexdigest(),
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
    }
    atomic_json(Path(args.context), value)
    print(f"PASS JIT fixture prepared jti={jti}")


def voice(args, expected):
    context = json.loads(Path(args.context).read_text(encoding="utf-8"))
    client = Client(args.workload_secrets)
    result = client.post(8085, "/v1/voice/calls", {
        "tenant_id": context["tenant_id"], "contact_id": context["contact_id"],
        "campaign_version_id": context["campaign_version_id"], "content_hash": context["content_hash"],
        "recipient_e164": "+525500000000", "authorization_token": context["token"],
    }, expect=expected)
    if expected == 202 and result.get("status") != "SHADOW_ACCEPTED":
        raise RuntimeError("VOICE_SHADOW_RECEIPT_INVALID")
    if expected == 409 and result.get("error") != "TOKEN_REPLAY":
        raise RuntimeError("VOICE_REPLAY_NOT_BLOCKED")
    label = "first-use" if expected == 202 else "post-restart replay"
    print(f"PASS voice {label}")


def parser():
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("workflow-before", "workflow-after"):
        command = sub.add_parser(name)
        command.add_argument("--workload-secrets", required=True)
        command.add_argument("--context", required=True)
        if name == "workflow-before":
            command.add_argument("--tenant", required=True)
            command.add_argument("--campaign-version", required=True)
            command.add_argument("--contact", required=True)
    make = sub.add_parser("make-token")
    make.add_argument("--decision", required=True)
    make.add_argument("--jit-secret", required=True)
    make.add_argument("--context", required=True)
    for name in ("voice-before", "voice-after"):
        command = sub.add_parser(name)
        command.add_argument("--workload-secrets", required=True)
        command.add_argument("--context", required=True)
    return result


def main():
    args = parser().parse_args()
    if args.command == "workflow-before": workflow_before(args)
    elif args.command == "workflow-after": workflow_after(args)
    elif args.command == "make-token": make_token(args)
    elif args.command == "voice-before": voice(args, 202)
    elif args.command == "voice-after": voice(args, 409)


if __name__ == "__main__": main()
