import random
import time
from dataclasses import dataclass


class PermanentFailure(RuntimeError): pass
class TransientFailure(RuntimeError): pass
class PolicyDenial(PermanentFailure): pass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_seconds: float = 0.5
    max_seconds: float = 30.0

    def delay(self, attempt: int, random_value=None) -> float:
        jitter = random.random() if random_value is None else random_value
        return min(self.max_seconds, self.base_seconds * (2 ** max(0, attempt - 1))) * (0.5 + jitter / 2)


class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_seconds=30, clock=time.monotonic):
        self.threshold, self.recovery_seconds, self.clock = failure_threshold, recovery_seconds, clock
        self.failures, self.opened_at = 0, None

    def allow(self):
        if self.opened_at is None: return True
        if self.clock() - self.opened_at >= self.recovery_seconds:
            self.failures, self.opened_at = 0, None
            return True
        return False

    def success(self): self.failures, self.opened_at = 0, None
    def failure(self):
        self.failures += 1
        if self.failures >= self.threshold: self.opened_at = self.clock()


class OutboxWorker:
    """Runs preflight immediately before every effect and never retries policy denials."""

    def __init__(self, preflight, dispatch, retry_policy=RetryPolicy()):
        self.preflight, self.dispatch, self.retry_policy = preflight, dispatch, retry_policy
        self.dead_letters = []

    def process(self, item: dict) -> dict:
        if item.get("status") in {"SENT", "CANCELLED"}: return item
        attempts = int(item.get("attempts", 0))
        try:
            authorization = self.preflight(item)
            receipt = self.dispatch(item, authorization)
            return {**item, "status": "SENT", "receipt": receipt, "attempts": attempts + 1}
        except PolicyDenial as exc:
            blocked = {**item, "status": "BLOCKED", "error": str(exc), "attempts": attempts + 1}
            self.dead_letters.append(blocked)
            return blocked
        except PermanentFailure as exc:
            failed = {**item, "status": "DEAD", "error": str(exc), "attempts": attempts + 1}
            self.dead_letters.append(failed)
            return failed
        except TransientFailure as exc:
            attempts += 1
            if attempts >= self.retry_policy.max_attempts:
                failed = {**item, "status": "DEAD", "error": str(exc), "attempts": attempts}
                self.dead_letters.append(failed)
                return failed
            return {**item, "status": "RETRY", "error": str(exc), "attempts": attempts,
                    "retry_after_seconds": self.retry_policy.delay(attempts)}
