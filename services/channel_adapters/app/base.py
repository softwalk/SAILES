import json
import urllib.error
import urllib.request
import urllib.parse


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("PROVIDER_REDIRECT_DENIED")


class HttpTransport:
    def __init__(self, allowed_hosts: set[str]):
        self.allowed_hosts = allowed_hosts
        self.opener = urllib.request.build_opener(NoRedirect)

    def _validate(self, url: str):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.allowed_hosts or parsed.username or parsed.password:
            raise RuntimeError("PROVIDER_URL_NOT_ALLOWLISTED")

    def post_json(self, url: str, body: dict, headers: dict[str, str] | None = None) -> dict:
        self._validate(url)
        request = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
        try:
            with self.opener.open(request, timeout=20) as response:
                return json.load(response)
        except (urllib.error.URLError, ValueError) as exc:
            raise RuntimeError("PROVIDER_TRANSPORT_FAILURE") from exc

    def post_form(self, url: str, body: dict, headers: dict[str, str] | None = None) -> dict:
        self._validate(url)
        request = urllib.request.Request(url, urllib.parse.urlencode(body).encode(), {"Content-Type": "application/x-www-form-urlencoded", **(headers or {})})
        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read().decode()
            try: return json.loads(raw)
            except ValueError: return {"raw": raw}
        except urllib.error.URLError as exc:
            raise RuntimeError("PROVIDER_TRANSPORT_FAILURE") from exc
