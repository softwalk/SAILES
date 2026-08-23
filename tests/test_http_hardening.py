import socket
import threading
import time
import unittest

from atlantis_contracts.client import JsonServiceClient
from atlantis_contracts.http import JsonRouter, RequestContext
from atlantis_contracts.middleware import RateLimitMiddleware
from atlantis_contracts.persistence import MemoryIdempotencyStore


class HttpHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        cls.port = probe.getsockname()[1]
        probe.close()
        router = JsonRouter(
            service_name="http-test",
            idempotency_store=MemoryIdempotencyStore("http-test"),
        )

        @router.route("POST", "/v1/test")
        def endpoint(body):
            return 200, {"ok": bool(body)}

        cls.thread = threading.Thread(target=router.serve, args=(cls.port,), daemon=True)
        cls.thread.start()
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=.1):
                    return
            except OSError:
                time.sleep(.01)
        raise RuntimeError("HTTP_TEST_SERVER_NOT_READY")

    def raw_status(self, request: bytes) -> bytes:
        with socket.create_connection(("127.0.0.1", self.port), timeout=1) as connection:
            connection.sendall(request)
            return connection.recv(256).split(b"\r\n", 1)[0]

    def test_negative_content_length_is_rejected_without_blocking(self):
        status = self.raw_status(
            b"POST /v1/test HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: -1\r\n\r\n"
        )
        self.assertIn(b"400", status)

    def test_json_content_type_is_required(self):
        status = self.raw_status(
            b"POST /v1/test HTTP/1.1\r\nHost: localhost\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\n{}"
        )
        self.assertIn(b"415", status)

    def test_shadow_http_requires_explicit_hostname_allowlist(self):
        with self.assertRaisesRegex(ValueError, "MUST_USE_HTTPS"):
            JsonServiceClient("http://crm_api:8082", "policy", b"x" * 32)
        client = JsonServiceClient(
            "http://crm_api:8082", "policy", b"x" * 32,
            allow_http_hosts={"crm_api"},
        )
        self.assertEqual("http://crm_api:8082", client.base_url)

    def test_unsigned_service_header_cannot_evade_ip_rate_limit(self):
        limiter = RateLimitMiddleware(requests_per_minute=1, clock=lambda: 1)
        first = RequestContext(b"{}", {}, {"x-atlantis-service": "one"}, {}, "POST", "/x", "10.0.0.1")
        second = RequestContext(b"{}", {}, {"x-atlantis-service": "two"}, {}, "POST", "/x", "10.0.0.1")
        limiter(first)
        with self.assertRaisesRegex(PermissionError, "RATE_LIMIT_EXCEEDED"):
            limiter(second)


if __name__ == "__main__":
    unittest.main()
