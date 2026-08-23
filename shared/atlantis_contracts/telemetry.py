import json
import logging
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


PII_KEYS = re.compile(r"phone|email|name|address|token|secret|password|content", re.I)


def redact(value):
    if isinstance(value, dict): return {k: "[REDACTED]" if PII_KEYS.search(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list): return [redact(v) for v in value]
    return value


class JsonLogger:
    def __init__(self, name: str): self.logger = logging.getLogger(name)
    def emit(self, level: int, event: str, **fields):
        self.logger.log(level, json.dumps({"event": event, **redact(fields)}, separators=(",", ":")))


@dataclass
class Metrics:
    counters: dict[tuple[str, tuple], int] = field(default_factory=dict)
    timings_ms: dict[str, list[float]] = field(default_factory=dict)

    def increment(self, name: str, **labels):
        key = name, tuple(sorted(labels.items()))
        self.counters[key] = self.counters.get(key, 0) + 1

    @contextmanager
    def timer(self, name: str):
        started = time.perf_counter()
        try: yield
        finally: self.timings_ms.setdefault(name, []).append((time.perf_counter() - started) * 1000)

    def snapshot(self):
        return {"counters": {f"{n}{dict(labels)}": v for (n, labels), v in self.counters.items()},
                "timings_ms": {name: {"count": len(values), "max": max(values), "avg": sum(values)/len(values)} for name, values in self.timings_ms.items() if values}}
