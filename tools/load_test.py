#!/usr/bin/env python3
import hashlib
import hmac
import importlib.util
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


workflow = load("load_workflow", "services/orchestrator/app/workflow.py")
from atlantis_contracts import WebhookVerifier


def main():
    engine = workflow.WorkflowEngine()
    lock = threading.Lock()
    started = time.perf_counter()
    def graph(index):
        state = engine.start("tenant-load", "campaign-load", f"contact-{index}")
        with lock: return engine.transition(state, f"event-{index}").stage.value
    with ThreadPoolExecutor(max_workers=100) as pool:
        stages = list(pool.map(graph, range(100)))
    graph_seconds = time.perf_counter() - started

    seen, seen_lock = set(), threading.Lock()
    def remember(provider, event_id, body_hash):
        with seen_lock:
            key = provider, event_id
            if key in seen: return False
            seen.add(key); return True
    verifier, secret, body = WebhookVerifier({"meta": b"m"*32}, remember), b"m"*32, b'{"entry":[]}'
    signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=100) as pool:
        receipts = list(pool.map(lambda i: verifier.verify_meta(body, signature, f"evt-{i}"), range(100)))
    webhook_seconds = time.perf_counter() - started
    result = {"graphs":len(stages), "graphs_per_second":round(100/graph_seconds,1),
              "webhooks":len(receipts), "webhooks_per_second":round(100/webhook_seconds,1)}
    if min(result["graphs_per_second"], result["webhooks_per_second"]) < 100:
        raise SystemExit("LOAD_TARGET_NOT_MET: " + str(result))
    print(result)


if __name__ == "__main__": main()
