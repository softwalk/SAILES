from atlantis_contracts import TokenVerifier


class VoiceAdapter:
    audience = "voice-adapter"

    def __init__(self, verifier: TokenVerifier, transport, shadow_mode=True):
        self.verifier, self.transport, self.shadow_mode = verifier, transport, shadow_mode

    def originate(self, token: str, command: dict) -> dict:
        expected = {key: command[key] for key in ("tenant_id", "contact_id", "campaign_version_id", "content_hash")}
        claims = self.verifier.verify_and_consume(token, self.audience, expected)
        if claims.channel != "VOICE":
            raise PermissionError("CHANNEL_MISMATCH")
        if self.shadow_mode:
            return {"status": "SHADOW_ACCEPTED", "jti": claims.jti}
        return self.transport.originate(command, token)


class VicidialTransport:
    def __init__(self, http, api_url: str, user: str, password: str, source="atlantis"):
        if not api_url or not user or not password: raise RuntimeError("VICIDIAL_NOT_CONFIGURED")
        self.http, self.api_url, self.user, self.password, self.source = http, api_url, user, password, source

    def originate(self, command: dict, token: str) -> dict:
        body = {"source": self.source, "user": self.user, "pass": self.password,
                "function": "external_dial", "value": command["recipient_e164"],
                "phone_code": command.get("phone_code", "52"), "search": "YES",
                "preview": "NO", "focus": "YES", "atlantis_authorization": token}
        result = self.http.post_form(self.api_url, body)
        return {"status": "ACCEPTED", "provider": "vicidial", "provider_response": result}


class NeobotTransport:
    def __init__(self, http, endpoint: str, api_token: str):
        if not endpoint or not api_token: raise RuntimeError("NEOBOT_NOT_CONFIGURED")
        self.http, self.endpoint, self.api_token = http, endpoint, api_token

    def originate(self, command: dict, token: str) -> dict:
        result = self.http.post_json(self.endpoint, {**command, "outbound_authorization": token}, {"Authorization": f"Bearer {self.api_token}"})
        return {"status": "ACCEPTED", "provider": "atlantis-neobot", "provider_response": result}
