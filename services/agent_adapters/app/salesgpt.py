class SalesGPTPolicy:
    forbidden_actions = {"send_message", "place_call", "take_payment", "sign_contract"}
    sensitive_intents = {"HIGH_DISCOUNT", "LEGAL_TERMS", "PAYMENT", "GUARANTEE"}
    opt_out_phrases = {"no me contacten", "deja de escribir", "stop", "baja"}

    def evaluate(self, recommendation: dict) -> dict:
        action = recommendation.get("action", "recommend")
        if action in self.forbidden_actions:
            return {"status": "DENIED", "reason": "DIRECT_SIDE_EFFECT_FORBIDDEN"}
        text = recommendation.get("text", "").lower()
        if any(phrase in text for phrase in self.opt_out_phrases):
            return {"status": "SUPPRESS_NOW", "reason": "OPT_OUT_DETECTED"}
        if recommendation.get("intent") in self.sensitive_intents:
            return {"status": "HUMAN_REVIEW", "reason": "SENSITIVE_OPPORTUNITY"}
        return {"status": "RECOMMEND", "reason": "WITHIN_POLICY"}
