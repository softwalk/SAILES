import hashlib
import re


class PhoneError(ValueError): pass


def normalize_e164(value: str, default_country_code="52") -> str:
    raw = re.sub(r"[^0-9+]", "", value.strip())
    if raw.startswith("00"): raw = "+" + raw[2:]
    if not raw.startswith("+"):
        digits = re.sub(r"\D", "", raw)
        if default_country_code == "52" and len(digits) == 10:
            raw = "+52" + digits
        else:
            raw = "+" + default_country_code + digits
    if not re.fullmatch(r"\+[1-9]\d{7,14}", raw):
        raise PhoneError("INVALID_E164_PHONE")
    return raw


def phone_token(e164: str, tenant_pepper: bytes) -> str:
    if len(tenant_pepper) < 32:
        raise ValueError("PHONE_TOKEN_PEPPER_TOO_SHORT")
    return hashlib.sha256(tenant_pepper + normalize_e164(e164).encode()).hexdigest()
