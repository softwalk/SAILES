import json
import urllib.parse
import hashlib
import uuid
import decimal
import os
import socket
from dataclasses import dataclass
from dataclasses import asdict, is_dataclass
from datetime import datetime, date as datetime_date
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from .persistence import build_idempotency_store


@dataclass(frozen=True)
class RequestContext:
    body: bytes
    json: dict[str, Any]
    headers: dict[str, str]
    query: dict[str, list[str]]
    method: str
    path: str
    client_ip: str


@dataclass(frozen=True)
class RawResponse:
    body: bytes
    content_type: str = "text/plain; charset=utf-8"


def _json_default(value: Any):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (datetime, Enum)):
        return value.isoformat() if isinstance(value, datetime) else value.value
    # psycopg v3 devuelve tipos nativos de PostgreSQL (UUID, date, Decimal, etc.).
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime_date,)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return format(value, "f")
    raise TypeError(type(value).__name__)


class JsonRouter:
    def __init__(self, max_body_bytes: int = 1_048_576, service_name="atlantis-service", idempotency_store=None):
        self.routes: dict[tuple[str, str], tuple[Callable, bool]] = {}
        self.max_body_bytes = max_body_bytes
        self.middlewares: list[Callable[[RequestContext], None]] = []
        self.idempotent_paths: set[str] = set()
        self.idempotency_store = idempotency_store or build_idempotency_store(service_name)

    def use(self, middleware: Callable[[RequestContext], None]):
        self.middlewares.append(middleware)

    def require_idempotency(self, *paths: str):
        self.idempotent_paths.update(paths)

    def route(self, method: str, path: str, *, raw: bool = False):
        def register(fn):
            self.routes[(method.upper(), path)] = (fn, raw)
            return fn
        return register

    def serve(self, port: int, bind_host: str | None = None):
        router = self
        bind_host = bind_host or os.getenv("ATLANTIS_BIND_HOST", "127.0.0.1")
        read_timeout = float(os.getenv("ATLANTIS_HTTP_READ_TIMEOUT_SECONDS", "10"))

        class Handler(BaseHTTPRequestHandler):
            server_version = "Atlantis"
            sys_version = ""

            def setup(self):
                super().setup()
                self.connection.settimeout(read_timeout)

            def _dispatch(self):
                route = router.routes.get((self.command, self.path.split("?", 1)[0]))
                if route is None:
                    return self._reply(404, {"error": "NOT_FOUND"})
                reservation = None
                try:
                    fn, wants_raw = route
                    content_length = self.headers.get("Content-Length")
                    if self.command == "POST" and content_length is None:
                        return self._reply(411, {"error": "CONTENT_LENGTH_REQUIRED"})
                    try:
                        size = int(content_length or "0")
                    except ValueError:
                        return self._reply(400, {"error": "CONTENT_LENGTH_INVALID"})
                    if size < 0:
                        return self._reply(400, {"error": "CONTENT_LENGTH_INVALID"})
                    if size > router.max_body_bytes:
                        return self._reply(413, {"error": "PAYLOAD_TOO_LARGE"})
                    if self.command == "POST":
                        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                        if content_type != "application/json":
                            return self._reply(415, {"error": "CONTENT_TYPE_MUST_BE_APPLICATION_JSON"})
                    raw_body = self.rfile.read(size) or b"{}"
                    body = json.loads(raw_body)
                    if not isinstance(body, dict):
                        return self._reply(400, {"error": "JSON_OBJECT_REQUIRED"})
                    parsed = urllib.parse.urlsplit(self.path)
                    context = RequestContext(raw_body, body, {k.lower(): v for k, v in self.headers.items()},
                                             urllib.parse.parse_qs(parsed.query), self.command, parsed.path, self.client_address[0])
                    for middleware in router.middlewares:
                        middleware(context)
                    cache_key = None
                    if self.command == "POST" and parsed.path in router.idempotent_paths:
                        idem_key = context.headers.get("idempotency-key", "")
                        if not 16 <= len(idem_key) <= 128:
                            return self._reply(400, {"error": "IDEMPOTENCY_KEY_REQUIRED"})
                        tenant_id = str(body.get("tenant_id", ""))
                        if not tenant_id:
                            return self._reply(400, {"error": "TENANT_ID_REQUIRED"})
                        body_hash = hashlib.sha256(raw_body).hexdigest()
                        state, cached = router.idempotency_store.claim(tenant_id, idem_key, body_hash)
                        if state == "CONFLICT":
                            return self._reply(409, {"error": "IDEMPOTENCY_KEY_CONFLICT"})
                        if state == "PENDING":
                            return self._reply(409, {"error": "IDEMPOTENCY_REQUEST_IN_PROGRESS"})
                        if state == "CACHED":
                            return self._reply(cached[0], cached[1])
                        reservation = tenant_id, idem_key, body_hash
                    if wants_raw:
                        status, result = fn(context)
                    else:
                        status, result = fn(body)
                except PermissionError as exc:
                    status, result = 403, {"error": str(exc)}
                except ValueError as exc:
                    status, result = 400, {"error": str(exc)}
                except (TimeoutError, socket.timeout):
                    status, result = 408, {"error": "REQUEST_TIMEOUT"}
                except Exception:
                    status, result = 500, {"error": "INTERNAL_ERROR"}
                if reservation and status < 500:
                    router.idempotency_store.finish(*reservation, status, result)
                elif reservation:
                    router.idempotency_store.abandon(*reservation)
                self._reply(status, result)

            do_GET = _dispatch
            do_POST = _dispatch

            def _reply(self, status: int, value: Any):
                if isinstance(value, RawResponse):
                    payload, content_type = value.body, value.content_type
                else:
                    payload, content_type = json.dumps(value, default=_json_default).encode(), "application/json"
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, fmt, *args):
                return

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        Server((bind_host, port), Handler).serve_forever()
