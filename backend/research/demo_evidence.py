"""Synthetic evidence generator for the Condition B demo only."""

import hashlib

VARIANTS = ("B1_SEC_STYLE", "B2_MARKET_STYLE", "B3_COMBINED")


def _stable_value(claim_id, variant):
    digest = hashlib.sha256(f"{claim_id}:{variant}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def get_demo_evidence(claim_id, claim_text, claim_date, variant):
    """Return synthetic demo evidence for the B-condition fallback.

    The `relevance` value is a deterministic metadata indicator derived from the
    claim ID and variant; it is not a learned relevance score or an externally
    calibrated rating. It is included only as diagnostic metadata for the demo.
    """
    if variant not in VARIANTS:
        raise ValueError(f"Unknown demo evidence variant: {variant}")
    if not claim_text.strip():
        raise ValueError("Claim text is required.")

    value = _stable_value(claim_id, variant)
    relevance = round(0.55 + (value % 40) / 100, 2)
    evidence_date = claim_date or "unknown"
    items = []
    if variant in {"B1_SEC_STYLE", "B3_COMBINED"}:
        items.append({
            "source": "Synthetic SEC-style demo source",
            "evidence_text": "Demonstration-only filing-style record generated from the claim identifier; this is not a real SEC response.",
            "evidence_date": evidence_date,
            "relevance": relevance,
            "temporal_status": "valid" if claim_date else "unavailable",
        })
    if variant in {"B2_MARKET_STYLE", "B3_COMBINED"}:
        items.append({
            "source": "Synthetic market-data-style demo source",
            "evidence_text": "Demonstration-only market-data record generated deterministically; this is not a real Alpha Vantage response.",
            "evidence_date": evidence_date,
            "relevance": round(max(0.5, relevance - 0.04), 2),
            "temporal_status": "valid" if claim_date else "unavailable",
        })
    return items
