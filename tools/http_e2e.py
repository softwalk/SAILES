#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET = "s" * 32


def request(method, url, body=None, idem=None):
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type":"application/json"}
    if idem: headers["Idempotency-Key"] = idem
    req = urllib.request.Request(url, payload, headers, method=method)
    with urllib.request.urlopen(req, timeout=3) as response:
        raw = response.read()
        return response.status, json.loads(raw) if raw else {}


def wait_health(url):
    for _ in range(30):
        try:
            if request("GET", url)[0] == 200: return
        except Exception: time.sleep(.1)
    raise RuntimeError("SERVICE_NOT_READY:" + url)


def main():
    base_env = {**os.environ, "ATLANTIS_JIT_SECRET":SECRET, "ATLANTIS_SHADOW_MODE":"true"}
    policy_env = {**base_env, "PYTHONPATH":f"{ROOT/'shared'}:{ROOT/'services/policy_gateway'}"}
    wa_env = {**base_env, "PYTHONPATH":f"{ROOT/'shared'}:{ROOT/'services/channel_adapters'}", "ADAPTER_MODE":"whatsapp"}
    processes = [
        subprocess.Popen([sys.executable,"-m","app.server"],cwd=ROOT,env=policy_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL),
        subprocess.Popen([sys.executable,"-m","app.server"],cwd=ROOT,env=wa_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL),
    ]
    try:
        wait_health("http://127.0.0.1:8081/health"); wait_health("http://127.0.0.1:8086/health")
        content_hash = "a"*64
        intent = {"tenant_id":"t1","contact_id":"c1","campaign_version_id":"v1","purpose":"PROMOTIONAL","channel":"WHATSAPP",
                  "content_hash":content_hash,"requested_at":"2026-08-22T12:00:00+00:00","campaign_approved":True,
                  "approved_content_hash":content_hash,"consent_active":True,"template_approved":True,
                  "conversation_window_open":False,"local_hour":12}
        _, decision = request("POST","http://127.0.0.1:8081/v1/contactability/decisions",intent,"decision-key-0001")
        _, cached = request("POST","http://127.0.0.1:8081/v1/contactability/decisions",intent,"decision-key-0001")
        assert cached["decision_id"] == decision["decision_id"]
        try:
            request("POST","http://127.0.0.1:8081/v1/contactability/decisions",{**intent,"content_hash":"b"*64},"decision-key-0001")
        except urllib.error.HTTPError as exc: assert exc.code == 409
        else: raise AssertionError("IDEMPOTENCY_CONFLICT_NOT_BLOCKED")
        _, auth = request("POST","http://127.0.0.1:8081/v1/outbound-authorizations",
                          {"tenant_id":"t1","decision_id":decision["decision_id"],"audience":"whatsapp-adapter"},"authorization-0001")
        command = {"authorization_token":auth["token"],"tenant_id":"t1","contact_id":"c1","campaign_version_id":"v1","content_hash":content_hash}
        _, receipt = request("POST","http://127.0.0.1:8086/v1/whatsapp/messages",command,"dispatch-key-0001")
        try: request("POST","http://127.0.0.1:8086/v1/whatsapp/messages",command,"dispatch-key-0002")
        except urllib.error.HTTPError as exc: assert exc.code == 409
        else: raise AssertionError("TOKEN_REPLAY_NOT_BLOCKED")
        print({"policy":decision["outcome"],"dispatch":receipt["status"],"idempotency":"PASS","replay":"BLOCKED"})
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: process.kill()


if __name__ == "__main__": main()
