import re

HIGH_RISK_PATTERNS = [
    r"brake failure",
    r"car won.?t stop",
    r"smoke",
    r"fire",
    r"accident",
    r"unsafe to drive",
    r"payment dispute",
    r"warranty dispute",
]

def requires_human(message: str) -> bool:
    text = message.lower()
    return any(re.search(p, text) for p in HIGH_RISK_PATTERNS)

def safe_customer_id(customer_id: str) -> str:
    # For a real deployment, map phone/email to an internal customer token.
    return customer_id.strip()[:128]
