#!/usr/bin/env python3
"""Low-cost shadow soak: health sampling plus bounded synthetic model calls."""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from pilot_live_probe import Client  # noqa: E402


PORTS = (8081, 8082, 8083, 8084, 8085, 8086, 8087)


def health(port: int):
    started = time.perf_counter()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
        body = json.load(response)
    if response.status != 200 or body.get("status") != "ok":
        raise RuntimeError(f"HEALTH_{port}_FAILED")
    return int((time.perf_counter() - started) * 1000)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=240)
    parser.add_argument("--health-interval", type=float, default=30)
    parser.add_argument("--model-interval", type=float, default=900)
    parser.add_argument("--max-model-calls", type=int, default=16)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--workload-secrets", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.minutes <= 0 or args.health_interval < 1 or args.model_interval < 1 or args.max_model_calls < 0:
        raise SystemExit("invalid soak bounds")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    client = Client(args.workload_secrets)
    started = time.monotonic()
    deadline = started + args.minutes * 60
    next_model = started
    samples = model_calls = failures = 0
    latency_max = 0
    with output.open("a", encoding="utf-8") as evidence:
        while time.monotonic() < deadline:
            record = {"timestamp": int(time.time()), "type": "health"}
            try:
                latencies = {str(port): health(port) for port in PORTS}
                latency_max = max(latency_max, *latencies.values())
                record["latency_ms"] = latencies
                record["status"] = "PASS"
            except Exception as exc:
                failures += 1
                record.update(status="FAIL", error=type(exc).__name__)
            evidence.write(json.dumps(record, separators=(",", ":")) + "\n")
            evidence.flush()
            samples += 1

            now = time.monotonic()
            if model_calls < args.max_model_calls and now >= next_model:
                call_started = time.perf_counter()
                try:
                    result = client.post(8084, "/v1/models/complete", {
                        "tenant_id": args.tenant, "task_alias": "shadow_soak",
                        "prompt": 'Synthetic shadow probe. Return JSON exactly with key "status" and value "ok".',
                        "data_classification": "INTERNAL", "max_cost_units": 300,
                        "expected_schema": ["status"], "correlation_id": str(uuid4()),
                        "prompt_version": "shadow-soak@1",
                    }, expect=200)
                    model_record = {
                        "timestamp": int(time.time()), "type": "model", "status": "PASS",
                        "provider": result.get("provider"), "model_id": result.get("model_id"),
                        "cost_units": result.get("cost_units"),
                        "latency_ms": int((time.perf_counter() - call_started) * 1000),
                    }
                except Exception as exc:
                    failures += 1
                    model_record = {"timestamp": int(time.time()), "type": "model", "status": "FAIL",
                                    "error": type(exc).__name__}
                evidence.write(json.dumps(model_record, separators=(",", ":")) + "\n")
                evidence.flush()
                model_calls += 1
                next_model = now + args.model_interval
            time.sleep(min(args.health_interval, max(0.0, deadline - time.monotonic())))

        summary = {"type": "summary", "status": "PASS" if failures == 0 else "FAIL",
                   "duration_minutes": round((time.monotonic() - started) / 60, 2),
                   "health_samples": samples, "model_calls": model_calls,
                   "failures": failures, "max_health_latency_ms": latency_max,
                   "external_contacts_executed": 0}
        evidence.write(json.dumps(summary, separators=(",", ":")) + "\n")
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if failures == 0 else 1)


if __name__ == "__main__": main()
