"""Deterministic fallback verifier for software demonstration only."""

import hashlib

SAFE_FIELDS = {"claim_id", "claim_text", "claim_date"}
PREDICTION_MODE = "DEMO_FALLBACK"
MODEL_NAME = "deterministic-demo-verifier"


def _bucket(text):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 3


def verify_claim(claim_id, claim_text, claim_date, evidence=None):
    """Predict from safe claim input and optional synthetic evidence only.

    This function intentionally never loads Fin-Fact records or gold labels.
    """
    safe_input = {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "claim_date": claim_date,
    }
    if set(safe_input) != SAFE_FIELDS:
        raise ValueError("Demo verifier received an unsafe input shape.")
    if not isinstance(claim_text, str) or not claim_text.strip():
        raise ValueError("Claim text is required.")

    text = claim_text.lower()
    evidence_text = " ".join(item.get("evidence_text", "") for item in evidence or [])
    signal_text = f"{text}|{claim_date or 'no-date'}|{evidence_text.lower()}"
    signal_bucket = _bucket(signal_text)
    if evidence:
        label = ("SUPPORTED", "REFUTED", "UNVERIFIABLE")[signal_bucket]
        confidence = (0.74, 0.71, 0.56)[signal_bucket]
        explanation = "Deterministic demonstration verdict derived from the supplied synthetic evidence pattern."
    elif any(word in text for word in ("scam", "fake", "hoax", "false", "did not")):
        label, confidence = "REFUTED", 0.62
        explanation = "Deterministic demonstration rule detected language associated with a disputed claim."
    elif any(char.isdigit() for char in text):
        label, confidence = ("SUPPORTED", 0.59) if signal_bucket == 0 else ("UNVERIFIABLE", 0.51)
        explanation = "Deterministic demonstration rule used the claim text, date, and stable hash bucket."
    else:
        label = ("SUPPORTED", "REFUTED", "UNVERIFIABLE")[signal_bucket]
        confidence = (0.57, 0.55, 0.5)[signal_bucket]
        explanation = "Deterministic demonstration rule used a stable hash of the safe claim input."

    return {
        "predicted_label": label,
        "confidence": confidence,
        "explanation": explanation,
        "prediction_mode": PREDICTION_MODE,
        "model": MODEL_NAME,
    }
