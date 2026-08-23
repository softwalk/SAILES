from datetime import UTC, datetime
from uuid import uuid4

from atlantis_contracts import Channel, ContactabilityRequest, Decision, DecisionOutcome


class PolicyEngine:
    """Deterministic, versioned and fail-closed contactability policy."""

    def __init__(self, policy_version: str = "mx-contactability@1", allowed_hours=(9, 20)):
        self.policy_version = policy_version
        self.allowed_hours = allowed_hours

    def decide(self, request: ContactabilityRequest) -> Decision:
        reasons: list[str] = []
        if request.kill_switch:
            reasons.append("GLOBAL_KILL_SWITCH")
        if not request.campaign_approved:
            reasons.append("CAMPAIGN_NOT_APPROVED")
        if request.approved_content_hash != request.content_hash:
            reasons.append("CAMPAIGN_CONTENT_CHANGED")
        if request.internally_suppressed:
            reasons.append("INTERNAL_SUPPRESSION")
        if request.frequency_exhausted:
            reasons.append("FREQUENCY_LIMIT")
        if request.local_hour is None:
            reasons.append("LOCAL_TIME_UNKNOWN")
        elif not self.allowed_hours[0] <= request.local_hour < self.allowed_hours[1]:
            reasons.append("OUTSIDE_ALLOWED_HOURS")

        promotional = request.purpose.upper() in {"PROMOTIONAL", "MARKETING", "SALES"}
        if request.channel == Channel.VOICE and promotional:
            if request.repep_snapshot_valid is not True:
                reasons.append("REPEP_EVIDENCE_MISSING_OR_STALE")
            elif request.repep_listed is not False:
                reasons.append("REPEP_LISTED_OR_UNKNOWN")
        if request.channel == Channel.WHATSAPP and promotional:
            if request.consent_active is not True:
                reasons.append("WHATSAPP_OPT_IN_MISSING")
            if request.conversation_window_open is not True and request.template_approved is not True:
                reasons.append("WHATSAPP_TEMPLATE_OR_WINDOW_INVALID")

        outcome = DecisionOutcome.DENY if reasons else DecisionOutcome.ALLOW
        return Decision(
            decision_id=str(uuid4()), outcome=outcome, reason_codes=tuple(reasons or ["POLICY_ALLOW"]),
            policy_version=self.policy_version, decided_at=datetime.now(UTC),
            evidence={"channel": request.channel.value, "campaign_version_id": request.campaign_version_id},
        )
