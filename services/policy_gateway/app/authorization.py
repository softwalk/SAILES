import time
from collections import OrderedDict
from threading import Lock
from uuid import uuid4

from atlantis_contracts import AuthorizationClaims, ContactabilityRequest, Decision, DecisionOutcome
from atlantis_contracts.token import sign_claims


class InMemoryReplayLedger:
    """Development ledger. Production must use an atomic PostgreSQL consume operation."""

    def __init__(self):
        self._issued: set[str] = set()
        self._consumed: set[str] = set()
        self._lock = Lock()

    def register(self, jti: str, claims=None, token_hash: str | None = None):
        with self._lock:
            self._issued.add(jti)

    def consume(self, jti: str, claims=None) -> bool:
        with self._lock:
            if jti not in self._issued or jti in self._consumed:
                return False
            self._consumed.add(jti)
            return True


class AuthorizationIssuer:
    def __init__(self, secret: bytes, ledger: InMemoryReplayLedger, issuer="atlantis-policy-gateway",
                 max_decision_age_seconds=120):
        if len(secret) < 32:
            raise ValueError("JIT secret must contain at least 32 bytes")
        if not 1 <= max_decision_age_seconds <= 300:
            raise ValueError("DECISION_MAX_AGE_OUT_OF_RANGE")
        self.secret, self.ledger, self.issuer = secret, ledger, issuer
        self.max_decision_age_seconds = max_decision_age_seconds

    def issue(self, decision: Decision, request: ContactabilityRequest, audience: str, ttl_seconds=120, now=None) -> str:
        if decision.outcome != DecisionOutcome.ALLOW:
            raise PermissionError("DENIED_DECISION_CANNOT_BE_AUTHORIZED")
        if ttl_seconds < 1 or ttl_seconds > 300:
            raise ValueError("TTL_OUT_OF_RANGE")
        issued_at = int(time.time()) if now is None else now
        decision_time = int(decision.decided_at.timestamp())
        if issued_at - decision_time > self.max_decision_age_seconds or decision_time - issued_at > 30:
            raise PermissionError("DECISION_EXPIRED")
        expected_audience = request.channel.value.lower() + "-adapter"
        if audience != expected_audience:
            raise PermissionError("DECISION_AUDIENCE_MISMATCH")
        jti = str(uuid4())
        claims = AuthorizationClaims(
            jti=jti, iss=self.issuer, aud=audience, tenant_id=request.tenant_id,
            contact_id=request.contact_id, campaign_version_id=request.campaign_version_id,
            decision_id=decision.decision_id, channel=request.channel.value, purpose=request.purpose,
            content_hash=request.content_hash, iat=issued_at, exp=issued_at + ttl_seconds,
        )
        token = sign_claims(self.secret, claims)
        import hashlib
        self.ledger.register(jti, claims, hashlib.sha256(token.encode()).hexdigest())
        return token


class DecisionContextStore:
    """Bounded, one-shot authorization context; PostgreSQL keeps the audit record."""

    def __init__(self, ttl_seconds=120, max_entries=10_000, clock=time.time):
        self.ttl_seconds, self.max_entries, self.clock = ttl_seconds, max_entries, clock
        self._values, self._lock = OrderedDict(), Lock()

    def put(self, decision, request):
        now = self.clock()
        with self._lock:
            self._prune(now)
            self._values[decision.decision_id] = (decision, request, now + self.ttl_seconds)
            self._values.move_to_end(decision.decision_id)
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)

    def take(self, decision_id: str, tenant_id: str):
        now = self.clock()
        with self._lock:
            value = self._values.get(decision_id)
            if not value:
                return None
            decision, request, expires_at = value
            if request.tenant_id != tenant_id:
                raise PermissionError("DECISION_TENANT_MISMATCH")
            self._values.pop(decision_id, None)
            if expires_at <= now:
                raise PermissionError("DECISION_EXPIRED")
            return decision, request

    def _prune(self, now):
        for key in [key for key, value in self._values.items() if value[2] <= now]:
            self._values.pop(key, None)
