#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
assert_safe_root

compose exec -T model_gateway python - <<'PY'
import os
import socket
import sys
from urllib.parse import urlparse

providers = (
    ("openrouter", "OPENROUTER_MODEL_ID", "OPENROUTER_BASE_URL"),
    ("kimi", "KIMI_MODEL_ID", "KIMI_BASE_URL"),
    ("deepseek", "DEEPSEEK_MODEL_ID", "DEEPSEEK_BASE_URL"),
)

configured = 0
failures = []
for name, model_variable, url_variable in providers:
    model = os.getenv(model_variable, "UNSET").strip()
    if not model or model == "UNSET":
        continue
    configured += 1
    parsed = urlparse(os.getenv(url_variable, ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        failures.append(f"{name}:invalid-url")
        continue
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        with socket.create_connection((parsed.hostname, port), timeout=5):
            pass
        print(f"PASS provider={name} model={model} host={parsed.hostname} port={port} addresses={len(addresses)}")
    except OSError as exc:
        failures.append(f"{name}:{type(exc).__name__}")

if configured < 1:
    print("FAIL no model provider configured", file=sys.stderr)
    raise SystemExit(1)
if failures:
    print("FAIL provider connectivity=" + ",".join(failures), file=sys.stderr)
    raise SystemExit(1)
print(f"PASS configured provider connectivity={configured}")
PY
