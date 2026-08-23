from atlantis_contracts import TokenVerifier


class WhatsAppAdapter:
    audience = "whatsapp-adapter"

    def __init__(self, verifier: TokenVerifier, transport, shadow_mode=True):
        self.verifier, self.transport, self.shadow_mode = verifier, transport, shadow_mode

    def send(self, token: str, command: dict) -> dict:
        expected = {key: command[key] for key in ("tenant_id", "contact_id", "campaign_version_id", "content_hash")}
        claims = self.verifier.verify_and_consume(token, self.audience, expected)
        if claims.channel != "WHATSAPP":
            raise PermissionError("CHANNEL_MISMATCH")
        if self.shadow_mode:
            return {"status": "SHADOW_ACCEPTED", "jti": claims.jti}
        return self.transport.send(command, token)


class MetaCloudTransport:
    def __init__(self, http, graph_base_url: str, graph_version: str, phone_number_id: str, access_token: str):
        if not graph_version or graph_version == "UNSET" or not phone_number_id or not access_token:
            raise RuntimeError("META_CLOUD_API_NOT_CONFIGURED")
        self.http, self.url = http, f"{graph_base_url.rstrip('/')}/{graph_version}/{phone_number_id}/messages"
        self.access_token = access_token

    def send(self, command: dict, token: str) -> dict:
        recipient = command["recipient_e164"]
        if "template" in command:
            message = {"messaging_product": "whatsapp", "to": recipient, "type": "template", "template": command["template"]}
        else:
            message = {"messaging_product": "whatsapp", "to": recipient, "type": "text", "text": {"body": command["text"], "preview_url": False}}
        result = self.http.post_json(self.url, message, {"Authorization": f"Bearer {self.access_token}", "X-Atlantis-Authorization-Id": token.split(".", 1)[0][:32]})
        return {"status": "ACCEPTED", "provider": "meta-cloud", "provider_response": result}
