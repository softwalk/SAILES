import json
import os
import time
from threading import RLock
from pathlib import Path

from .security import WorkloadRequestVerifier
from .persistence import build_nonce_store


class WorkloadAuthMiddleware:
    def __init__(self, secrets: dict[str, bytes], exempt_paths=None, nonce_store=None):
        self.nonce_store = nonce_store or build_nonce_store()
        self.verifier = WorkloadRequestVerifier(secrets, self.nonce_store.remember)
        self.exempt_paths = exempt_paths or {"/health"}

    @classmethod
    def from_environment(cls, exempt_paths=None):
        path = os.getenv("ATLANTIS_WORKLOAD_SECRETS_FILE")
        if not path:
            raise RuntimeError("ATLANTIS_WORKLOAD_SECRETS_FILE_REQUIRED")
        values = json.loads(Path(path).read_text())
        return cls({key: value.encode() for key, value in values.items()}, exempt_paths, build_nonce_store())

    def __call__(self, request):
        request.headers.pop("x-atlantis-authenticated-service", None)
        if request.path in self.exempt_paths:
            return
        headers = request.headers
        tenant_id = str(request.json.get("tenant_id", ""))
        service_id = self.verifier.verify(
            headers.get("x-atlantis-service", ""), headers.get("x-atlantis-timestamp", ""),
            headers.get("x-atlantis-nonce", ""), headers.get("x-atlantis-signature", ""),
            request.method, request.path, request.body, tenant_id,
        )
        request.headers["x-atlantis-authenticated-service"] = service_id


def configure_workload_auth(router, exempt_paths=None):
    default = "true" if os.getenv("ATLANTIS_ENV", "development") != "development" else "false"
    if os.getenv("ATLANTIS_REQUIRE_WORKLOAD_AUTH", default).lower() == "true":
        router.use(WorkloadAuthMiddleware.from_environment(exempt_paths))


class RateLimitMiddleware:
    def __init__(self, requests_per_minute=600, exempt_paths=None, clock=time.monotonic):
        self.limit, self.exempt_paths, self.clock = requests_per_minute, exempt_paths or {"/health"}, clock
        self.windows, self.lock = {}, RLock()

    def __call__(self, request):
        if request.path in self.exempt_paths: return
        identity = request.headers.get("x-atlantis-authenticated-service") or request.client_ip
        minute = int(self.clock() // 60)
        key = identity, minute
        with self.lock:
            count = self.windows.get(key, 0) + 1
            self.windows[key] = count
            if len(self.windows) > 10_000:
                self.windows = {k:v for k,v in self.windows.items() if k[1] >= minute-1}
        if count > self.limit:
            raise PermissionError("RATE_LIMIT_EXCEEDED")


def configure_rate_limit(router):
    router.use(RateLimitMiddleware(int(os.getenv("ATLANTIS_RATE_LIMIT_PER_MINUTE", "600"))))
