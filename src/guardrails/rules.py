
import re, yaml

PII_PATTERNS = {
    "card": r"\b(?:\d[ -]*?){13,19}\b",
    "cvv": r"\b\d{3,4}\b",
    "phone": r"\+?\d[\d \-]{7,}\d",
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "passport": r"\b\d{2}\s?\d{2}\s?\d{6}\b"
}

def detect_pii(text: str):
    hits = []
    for name, pat in PII_PATTERNS.items():
        if re.search(pat, text):
            hits.append(name)
    return hits

def load_policy(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def violates_policy(text: str, policy: dict):
    phrases = [p.lower() for p in policy.get("forbidden_phrases", [])]
    low = text.lower()
    bad = [p for p in phrases if p in low]
    return bad
