from copy import deepcopy
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from atlantis_contracts import canonical_json, sha256_hex


class CRMStore:
    """Tenant-scoped dev repository mirroring PostgreSQL invariants."""

    def __init__(self):
        self._lock = RLock()
        self.contacts, self.campaigns, self.suppressions, self.consents = {}, {}, {}, {}
        self.interactions, self.opportunities, self.memory_facts = {}, {}, {}
        self.data_requests, self.legal_holds = {}, {}
        self.outbox, self.audit = [], []
        self.audit_heads: dict[str, dict] = {}

    def _key(self, tenant_id, item_id):
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        return tenant_id, item_id

    def create_contact(self, tenant_id: str, data: dict):
        contact_id = data.get("id", str(uuid4()))
        record = {"id": contact_id, "tenant_id": tenant_id, "version": 1, **deepcopy(data)}
        with self._lock:
            self.contacts[self._key(tenant_id, contact_id)] = record
            self._event(tenant_id, "contact.created", "contact", contact_id, record)
        return deepcopy(record)

    def create_campaign_version(self, tenant_id: str, campaign_id: str, manifest: dict):
        version_id = str(uuid4())
        canonical = canonical_json(manifest)
        record = {"id": version_id, "tenant_id": tenant_id, "campaign_id": campaign_id,
                  "manifest": deepcopy(manifest), "manifest_hash": sha256_hex(manifest),
                  "status": "PENDING_APPROVAL", "approved_hash": None, "version": 1}
        with self._lock:
            self.campaigns[self._key(tenant_id, version_id)] = record
            self._event(tenant_id, "campaign.version.created", "campaign_version", version_id, {"canonical": canonical})
        return deepcopy(record)

    def approve_campaign(self, tenant_id: str, version_id: str, approver_id: str, subject_hash: str,
                         approver_role: str = "CAMPAIGN_APPROVER", comment: str | None = None):
        with self._lock:
            row = self.campaigns[self._key(tenant_id, version_id)]
            if row["manifest_hash"] != subject_hash:
                raise ValueError("APPROVAL_HASH_MISMATCH")
            row.update(status="APPROVED", approved_hash=subject_hash, approved_by=approver_id,
                       approver_role=approver_role, approval_comment=comment)
            self._event(tenant_id, "campaign.version.approved", "campaign_version", version_id, {"approver_id": approver_id})
            return deepcopy(row)

    def amend_campaign(self, tenant_id: str, version_id: str, manifest: dict):
        with self._lock:
            row = self.campaigns[self._key(tenant_id, version_id)]
            row.update(manifest=deepcopy(manifest), manifest_hash=sha256_hex(manifest), status="PENDING_APPROVAL", approved_hash=None)
            row["version"] += 1
            self._event(tenant_id, "campaign.version.amended", "campaign_version", version_id, {})
            return deepcopy(row)

    def suppress(self, tenant_id: str, contact_id: str, reason="OPT_OUT"):
        with self._lock:
            self.suppressions[self._key(tenant_id, contact_id)] = {"active": True, "reason": reason}
            self._event(tenant_id, "contact.suppressed", "contact", contact_id, {"reason": reason})

    def grant_consent(self, tenant_id: str, contact_id: str, channel: str, evidence_hash: str):
        with self._lock:
            self.consents[(tenant_id, contact_id, channel)] = {"active": True, "evidence_hash": evidence_hash}
            self._event(tenant_id, "consent.granted", "contact", contact_id, {"channel": channel})

    def record_interaction(self, tenant_id: str, contact_id: str, data: dict):
        self._require_contact(tenant_id, contact_id)
        interaction_id = data.get("id", str(uuid4()))
        record = {"id": interaction_id, "tenant_id": tenant_id, "contact_id": contact_id,
                  "created_at": datetime.now(UTC).isoformat(), **deepcopy(data)}
        with self._lock:
            key = self._key(tenant_id, interaction_id)
            if key in self.interactions: return deepcopy(self.interactions[key])
            self.interactions[key] = record
            self._event(tenant_id, "interaction.recorded", "interaction", interaction_id, {"contact_id": contact_id})
        return deepcopy(record)

    def upsert_opportunity(self, tenant_id: str, contact_id: str, data: dict):
        self._require_contact(tenant_id, contact_id)
        opportunity_id = data.get("id", str(uuid4()))
        key = self._key(tenant_id, opportunity_id)
        with self._lock:
            previous = self.opportunities.get(key, {})
            record = {"id": opportunity_id, "tenant_id": tenant_id, "contact_id": contact_id,
                      "version": previous.get("version", 0) + 1, **deepcopy(data)}
            self.opportunities[key] = record
            self._event(tenant_id, "opportunity.upserted", "opportunity", opportunity_id, {"stage": record.get("stage")})
        return deepcopy(record)

    def add_memory_fact(self, tenant_id: str, contact_id: str, fact: dict):
        self._require_contact(tenant_id, contact_id)
        if fact.get("fact_kind") not in {"DECLARED", "OBSERVED", "INFERRED"}:
            raise ValueError("MEMORY_FACT_KIND_INVALID")
        if not 0 <= float(fact.get("confidence", -1)) <= 1:
            raise ValueError("MEMORY_CONFIDENCE_INVALID")
        fact_id = str(uuid4())
        record = {"id": fact_id, "tenant_id": tenant_id, "contact_id": contact_id, **deepcopy(fact)}
        with self._lock:
            self.memory_facts[self._key(tenant_id, fact_id)] = record
            self._event(tenant_id, "memory.fact.added", "memory_fact", fact_id, {"predicate": fact.get("predicate")})
        return deepcopy(record)

    def request_arco(self, tenant_id: str, contact_id: str, request_type: str, verification_ref: str):
        self._require_contact(tenant_id, contact_id)
        if request_type not in {"ACCESS", "RECTIFICATION", "CANCELLATION", "OPPOSITION", "REVOCATION", "PORTABILITY"}:
            raise ValueError("ARCO_TYPE_INVALID")
        request_id = str(uuid4())
        record = {"id": request_id, "tenant_id": tenant_id, "contact_id": contact_id,
                  "request_type": request_type, "identity_verification_ref": verification_ref, "status": "OPEN"}
        with self._lock:
            self.data_requests[self._key(tenant_id, request_id)] = record
            self._event(tenant_id, "privacy.request.opened", "data_subject_request", request_id, {"type": request_type})
        return deepcopy(record)

    def export_contact(self, tenant_id: str, contact_id: str) -> dict:
        contact = self._require_contact(tenant_id, contact_id)
        select = lambda rows: [deepcopy(v) for (tenant, _), v in rows.items() if tenant == tenant_id and v.get("contact_id") == contact_id]
        return {"contact": deepcopy(contact), "interactions": select(self.interactions),
                "opportunities": select(self.opportunities), "memory_facts": select(self.memory_facts),
                "consents": [deepcopy(v) for (tenant, cid, _), v in self.consents.items() if tenant == tenant_id and cid == contact_id],
                "suppression": deepcopy(self.suppressions.get(self._key(tenant_id, contact_id)))}

    def contactability_evidence(self, tenant_id: str, contact_id: str, phone_token: str | None, channel: str,
                                purpose: str, campaign_version_id: str) -> dict:
        self._require_contact(tenant_id, contact_id)
        campaign = self.campaigns.get(self._key(tenant_id, campaign_version_id), {})
        consent = self.consents.get((tenant_id, contact_id, channel), {})
        content_hashes = campaign.get("manifest", {}).get("content_hashes", {})
        repep = campaign.get("manifest", {}).get("repep", {})
        return {"suppressed":bool(self.suppressions.get(self._key(tenant_id, contact_id), {}).get("active", False)),
                "consent_active":bool(consent.get("active", False)),
                "campaign_approved":campaign.get("status") == "APPROVED" and bool(campaign.get("approved_hash")),
                "approved_content_hash":content_hashes.get(channel.lower()),
                "repep_snapshot_valid":False, "repep_listed":None,
                "repep_enabled":bool(repep.get("enabled", False)),
                "repep_exemption_type":repep.get("exemption_type"),
                "repep_exemption_approved":bool(repep.get("exemption_approved", False)),
                "repep_exemption_evidence_ref":repep.get("exemption_evidence_ref")}

    def export_audit(self, tenant_id: str) -> list[dict]:
        return [deepcopy(event) for event in self.audit if event["tenant_id"] == tenant_id]

    @staticmethod
    def verify_audit(events: list[dict]) -> bool:
        previous = None
        for expected_sequence, event in enumerate(events, 1):
            body = dict(event); supplied_hash = body.pop("event_hash", None)
            if body.get("sequence_no") != expected_sequence or body.get("previous_hash") != previous:
                return False
            if supplied_hash != sha256_hex(body): return False
            previous = supplied_hash
        return True

    def _require_contact(self, tenant_id, contact_id):
        record = self.contacts.get(self._key(tenant_id, contact_id))
        if record is None: raise KeyError("CONTACT_NOT_FOUND_IN_TENANT")
        return record

    def _event(self, tenant_id, event_type, aggregate_type, aggregate_id, payload):
        event_id = str(uuid4())
        event = {"id": event_id, "tenant_id": tenant_id, "event_type": event_type,
                 "aggregate_type": aggregate_type, "aggregate_id": aggregate_id,
                 "payload": deepcopy(payload), "occurred_at": datetime.now(UTC).isoformat()}
        self.outbox.append(event)
        head = self.audit_heads.get(tenant_id)
        previous = head["event_hash"] if head else None
        sequence = head["sequence_no"] + 1 if head else 1
        audit_body = {"sequence_no": sequence, "previous_hash": previous, **event}
        audit_body["event_hash"] = sha256_hex(audit_body)
        self.audit.append(audit_body)
        self.audit_heads[tenant_id] = audit_body
