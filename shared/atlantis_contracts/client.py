import json
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from uuid import uuid4

from .security import sign_workload_request


class ServiceClientError(RuntimeError): pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ServiceClientError("INTERNAL_SERVICE_REDIRECT_DENIED")


class JsonServiceClient:
    def __init__(self, base_url: str, service_id: str, secret: bytes, *, ca_file=None,
                 client_cert_file=None, client_key_file=None, allow_http_hosts=None):
        parsed = urlparse(base_url)
        allow_http_hosts = set(allow_http_hosts or ())
        secure = parsed.scheme == "https"
        shadow_http = parsed.scheme == "http" and parsed.hostname in allow_http_hosts
        if (not (secure or shadow_http) or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in {"", "/"}):
            raise ValueError("INTERNAL_SERVICE_URL_MUST_USE_HTTPS")
        if len(secret) < 32: raise ValueError("WORKLOAD_SECRET_TOO_SHORT")
        self.base_url, self.service_id, self.secret = base_url.rstrip("/"), service_id, secret
        handlers = [NoRedirect]
        if secure:
            context = ssl.create_default_context(cafile=ca_file)
            if client_cert_file:
                context.load_cert_chain(client_cert_file, client_key_file)
            handlers.append(urllib.request.HTTPSHandler(context=context))
        self.opener = urllib.request.build_opener(*handlers)

    def post(self, path: str, body: dict, idempotency_key: str | None = None) -> dict:
        if not body.get("tenant_id"):
            raise ValueError("WORKLOAD_TENANT_REQUIRED")
        payload = json.dumps(body, separators=(",",":"), sort_keys=True).encode()
        timestamp, nonce = int(time.time()), str(uuid4())
        signature = sign_workload_request(self.secret, timestamp, nonce, "POST", path, payload)
        headers = {"Content-Type":"application/json", "X-Atlantis-Service":self.service_id,
                   "X-Atlantis-Timestamp":str(timestamp), "X-Atlantis-Nonce":nonce,
                   "X-Atlantis-Signature":signature, "Idempotency-Key":idempotency_key or str(uuid4())}
        try:
            with self.opener.open(urllib.request.Request(self.base_url+path,payload,headers),timeout=5) as response:
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                if content_type != "application/json":
                    raise ServiceClientError("INTERNAL_SERVICE_CONTENT_TYPE_INVALID")
                size = int(response.headers.get("Content-Length", "0") or "0")
                if size < 0 or size > 1_048_576:
                    raise ServiceClientError("INTERNAL_SERVICE_RESPONSE_TOO_LARGE")
                payload = response.read(1_048_577)
                if len(payload) > 1_048_576:
                    raise ServiceClientError("INTERNAL_SERVICE_RESPONSE_TOO_LARGE")
                return json.loads(payload)
        except (urllib.error.URLError, ValueError) as exc:
            raise ServiceClientError("INTERNAL_SERVICE_FAILURE") from exc
