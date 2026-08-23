from atlantis_contracts import sha256_hex


class OpenSalesAdapter:
    """Generator-only boundary: no send, Sheets, payment or channel credentials."""

    allowed_outputs = {"segment", "sequence", "subject", "body", "claims"}

    def normalize_artifact(self, artifact: dict, grounded_claims: set[str]) -> dict:
        unknown = set(artifact) - self.allowed_outputs
        if unknown:
            raise ValueError("UNSUPPORTED_OPENSALES_OUTPUT")
        if any(claim not in grounded_claims for claim in artifact.get("claims", [])):
            raise ValueError("UNGROUNDED_CLAIM")
        return {**artifact, "artifact_hash": sha256_hex(artifact)}

    def material_diff(self, approved: dict, candidate: dict) -> dict:
        material_fields = {"segment", "sequence", "subject", "body", "claims"}
        changes = {key: {"before": approved.get(key), "after": candidate.get(key)}
                   for key in material_fields if approved.get(key) != candidate.get(key)}
        return {"material": bool(changes), "changes": changes,
                "approved_hash": sha256_hex(approved), "candidate_hash": sha256_hex(candidate)}
