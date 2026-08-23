from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Channel(StrEnum):
    VOICE = "VOICE"
    WHATSAPP = "WHATSAPP"


class DecisionOutcome(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class ContactabilityRequest:
    tenant_id: str
    contact_id: str
    campaign_version_id: str
    purpose: str
    channel: Channel
    content_hash: str
    requested_at: datetime
    campaign_approved: bool = False
    approved_content_hash: str | None = None
    internally_suppressed: bool = False
    frequency_exhausted: bool = False
    kill_switch: bool = False
    consent_active: bool | None = None
    template_approved: bool | None = None
    conversation_window_open: bool | None = None
    repep_snapshot_valid: bool | None = None
    repep_listed: bool | None = None
    local_hour: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    decision_id: str
    outcome: DecisionOutcome
    reason_codes: tuple[str, ...]
    policy_version: str
    decided_at: datetime
    evidence: dict[str, Any] = field(default_factory=dict)
