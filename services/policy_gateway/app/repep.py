from dataclasses import dataclass
from datetime import UTC, datetime

from atlantis_contracts import sha256_hex


@dataclass(frozen=True)
class RepepSnapshot:
    dataset_id: str
    tenant_id: str
    effective_at: datetime
    valid_until: datetime
    contract_or_receipt_ref: str
    evidence_uri: str
    evidence_hash: str
    phone_tokens: frozenset[str]


class RepepRegistry:
    """Imports only datasets obtained through an authorized offline mechanism."""

    def __init__(self): self.snapshots: dict[tuple[str, str], RepepSnapshot] = {}

    def import_snapshot(self, snapshot: RepepSnapshot, raw_bytes: bytes):
        if sha256_hex(raw_bytes) != snapshot.evidence_hash:
            raise ValueError("REPEP_EVIDENCE_HASH_MISMATCH")
        if not snapshot.contract_or_receipt_ref or not snapshot.evidence_uri:
            raise ValueError("REPEP_ACQUISITION_EVIDENCE_REQUIRED")
        if snapshot.valid_until <= snapshot.effective_at:
            raise ValueError("REPEP_VALIDITY_INVALID")
        self.snapshots[(snapshot.tenant_id, snapshot.dataset_id)] = snapshot

    def check(self, tenant_id: str, dataset_id: str, token: str, now=None) -> dict:
        clock = datetime.now(UTC) if now is None else now
        snapshot = self.snapshots.get((tenant_id, dataset_id))
        if snapshot is None:
            return {"snapshot_valid": False, "listed": None, "reason": "REPEP_SNAPSHOT_MISSING"}
        if not snapshot.effective_at <= clock < snapshot.valid_until:
            return {"snapshot_valid": False, "listed": None, "reason": "REPEP_SNAPSHOT_STALE"}
        return {"snapshot_valid": True, "listed": token in snapshot.phone_tokens,
                "dataset_id": dataset_id, "evidence_hash": snapshot.evidence_hash}
