from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse
import re


@dataclass(frozen=True)
class Lead:
    company: str
    contact_name: str | None
    website: str | None
    phone_token: str | None
    source_uri: str
    source_license: str
    observed_at: datetime
    confidence: float
    attributes: dict = field(default_factory=dict)


class LeadGovernance:
    def __init__(self, allowed_domains: set[str], allowed_licenses: set[str]):
        self.allowed_domains, self.allowed_licenses = allowed_domains, allowed_licenses

    def validate(self, lead: Lead):
        domain = urlparse(lead.source_uri).hostname
        if domain not in self.allowed_domains:
            raise PermissionError("LEAD_SOURCE_NOT_ALLOWLISTED")
        if lead.source_license not in self.allowed_licenses:
            raise PermissionError("LEAD_SOURCE_LICENSE_NOT_APPROVED")
        if not 0 <= lead.confidence <= 1:
            raise ValueError("LEAD_CONFIDENCE_INVALID")
        return lead


class LeadScorer:
    version = "lead-score@1"

    def score(self, lead: Lead, ideal_profile: dict) -> dict:
        components = {
            "industry": 35 if lead.attributes.get("industry") in ideal_profile.get("industries", []) else 0,
            "employee_range": 25 if ideal_profile.get("min_employees", 0) <= lead.attributes.get("employees", -1) <= ideal_profile.get("max_employees", 10**9) else 0,
            "region": 20 if lead.attributes.get("region") in ideal_profile.get("regions", []) else 0,
            "source_confidence": round(20 * lead.confidence),
        }
        return {"score": sum(components.values()), "components": components, "version": self.version}


class LeadDeduplicator:
    def classify(self, left: Lead, right: Lead) -> str:
        if left.phone_token and left.phone_token == right.phone_token: return "MATCH"
        if left.website and right.website and urlparse(left.website).hostname == urlparse(right.website).hostname: return "REVIEW"
        if left.company.strip().casefold() == right.company.strip().casefold(): return "REVIEW"
        return "DISTINCT"


class UntrustedContentGuard:
    patterns = [re.compile(p, re.I) for p in (
        r"ignore (all |the )?(previous|prior) instructions",
        r"system prompt", r"developer message", r"tool[_ ]?call", r"execute\s+(command|shell|code)",
        r"reveal\s+(secret|token|password)",
    )]

    def inspect(self, text: str) -> dict:
        findings = [pattern.pattern for pattern in self.patterns if pattern.search(text)]
        return {"status":"QUARANTINE" if findings else "ALLOW", "findings":findings,
                "content_hash":__import__("hashlib").sha256(text.encode()).hexdigest()}
