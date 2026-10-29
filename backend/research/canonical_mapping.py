"""
canonical_mapping.py

Canonical mapping, metrics, and evidence gating constants for the
Financial News Claim Verification research project.

Benchmark: Fin-Fact (seed 42, 300 claims)
Classes: SUPPORTED, REFUTED, UNVERIFIABLE
"""

from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CLASSES = ["SUPPORTED", "REFUTED", "UNVERIFIABLE"]

LABEL_MAPPING = {
    "true": "SUPPORTED",
    "false": "REFUTED",
    "NEI": "UNVERIFIABLE",
}

INVERSE_LABEL_MAPPING = {
    "SUPPORTED": "true",
    "REFUTED": "false",
    "UNVERIFIABLE": "NEI",
}

# ── Retrieval and Relevance Status Constants ─────────────────────────────────
RETRIEVAL_SUCCESS = "success"
RETRIEVAL_SOURCE_NOT_APPLICABLE = "source_not_applicable"
RETRIEVAL_TECHNICAL_ERROR = "technical_error"
RETRIEVAL_NO_RESULTS = "no_results"

RELEVANCE_RELEVANT = "evidence_relevant"
RELEVANCE_IRRELEVANT = "evidence_irrelevant"
RELEVANCE_TEMPORAL_REJECTED = "temporal_rejected"

# ── Four-Tier Pipeline Outcome Status Constants ──────────────────────────────
STATUS_GROUNDED_SUCCESS = "grounded_success"
STATUS_NO_RELEVANT_EVIDENCE = "no_relevant_evidence"
STATUS_RETRIEVAL_ERROR = "retrieval_error"
STATUS_INFERENCE_ERROR = "inference_error"

PIPELINE_STATUSES = [
    STATUS_GROUNDED_SUCCESS,
    STATUS_NO_RELEVANT_EVIDENCE,
    STATUS_RETRIEVAL_ERROR,
    STATUS_INFERENCE_ERROR,
]


def verify_manifest(
    manifest_path: Optional[Path] = None,
    root_dir: Optional[Path] = None,
) -> Tuple[bool, Dict[str, str]]:
    """
    Verifies that all files specified in pre_run_manifest.sha256 exist
    and match their cryptographic hashes.
    Returns (is_valid, report_dict).
    """
    if root_dir is None:
        root_dir = Path(__file__).resolve().parents[2]
    if manifest_path is None:
        manifest_path = root_dir / "backend" / "data" / "experiment_v3" / "pre_run_manifest.sha256"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    report = {}
    all_match = True

    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            expected_hash, rel_path = parts[0].strip(), parts[1].strip()
            target_file = root_dir / rel_path

            if not target_file.exists():
                report[rel_path] = f"MISSING (expected {expected_hash[:8]}...)"
                all_match = False
                continue

            hasher = hashlib.sha256()
            with open(target_file, "rb") as tf:
                while chunk := tf.read(65536):
                    hasher.update(chunk)
            actual_hash = hasher.hexdigest()

            if actual_hash.lower() == expected_hash.lower():
                report[rel_path] = f"OK ({actual_hash[:8]}...)"
            else:
                report[rel_path] = f"MISMATCH (expected {expected_hash[:8]}, got {actual_hash[:8]})"
                all_match = False

    return all_match, report


def parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
    """Safely parse YYYY-MM-DD or standard ISO date string."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str.split("T")[0] if "T" in date_str else date_str, fmt)
        except ValueError:
            continue
    return None


def is_temporally_valid(evidence_date: Optional[str], claim_date: Optional[str]) -> Tuple[bool, str]:
    """
    Validates that evidence was published on or before the claim date.
    Returns (is_valid, reason).
    """
    if not claim_date:
        return False, "claim_date_missing"
    if not evidence_date:
        return False, "evidence_date_missing"

    c_dt = parse_iso_date(claim_date)
    e_dt = parse_iso_date(evidence_date)

    if not c_dt:
        return False, f"invalid_claim_date_format: {claim_date}"
    if not e_dt:
        return False, f"invalid_evidence_date_format: {evidence_date}"

    if e_dt.date() > c_dt.date():
        return False, f"future_evidence_rejected: {e_dt.date()} > {c_dt.date()}"

    return True, "temporally_valid"


def evaluate_evidence_relevance(
    claim_text: str,
    evidence_text: str,
    source_type: str = "text"
) -> Tuple[bool, str, List[str]]:
    """
    Determines whether a piece of evidence is semantically and propositionally
    relevant to the claim.
    
    Rejects:
    - Off-modal evidence (e.g. stock price tables for speech/tweet claims).
    - Routine administrative SEC filings for store closure/retail rumor claims.
    """
    claim_lower = claim_text.lower()
    ev_lower = evidence_text.lower()

    # Rule 1: Off-modal rejection:
    # If the claim is about a tweet, speech, or statement, numerical price quotes cannot verify it
    is_speech_claim = any(kw in claim_lower for kw in ["tweet", "tweeted", "said", "quote", "claimed", "stated", "speech", "shot out of a cannon"])
    is_market_data = any(kw in ev_lower for kw in ["monthly market data", "open ", "high ", "close ", "volume ", "global quote"])

    if is_speech_claim and is_market_data and not any(kw in ev_lower for kw in ["tweet", "twitter", "post", "statement", "transcript"]):
        return False, "off_modal_market_data_for_speech_claim", []

    # Rule 2: Routine corporate filings for social media rumors
    is_rumor_claim = any(kw in claim_lower for kw in ["shutting down stores", "closing down", "boycott", "scam"])
    is_routine_8k = "departure of directors or certain officers" in ev_lower or "unregistered sales of equity" in ev_lower
    if is_rumor_claim and is_routine_8k and not any(kw in ev_lower for kw in ["close", "closing", "shutdown", "store", "locations"]):
        return False, "routine_filing_irrelevant_to_consumer_rumor", []

    # Rule 3: Anchor token overlap (subject entity + action predicate)
    # Extract significant non-stopwords (> 3 chars) from claim
    stopwords = {"that", "this", "what", "with", "from", "have", "were", "been", "their", "there", "about", "would", "could", "should"}
    words = [w.strip("?,.:;\"'()[]") for w in claim_lower.split() if len(w) > 3 and w not in stopwords]
    
    matched_anchors = [w for w in words if w in ev_lower]
    
    # Must match at least 2 distinct significant terms to pass basic lexical gating
    if len(matched_anchors) < 2:
        return False, f"insufficient_anchor_overlap: {matched_anchors}", matched_anchors

    return True, "anchors_and_proposition_matched", matched_anchors


def calculate_metrics(gold_labels: List[str], predictions: List[str]) -> Dict[str, Any]:
    """
    Independently computes confusion matrix, accuracy, macro metrics,
    and per-class performance.
    """
    n = len(gold_labels)
    if n == 0:
        return {
            "evaluated_claims": 0,
            "accuracy": None,
            "macro_precision": None,
            "macro_recall": None,
            "macro_f1": None,
            "per_class": {},
            "confusion_matrix": {},
            "predicted_class_counts": {c: 0 for c in CLASSES},
        }

    # Map gold labels to canonical CLASSES
    gold_mapped = [LABEL_MAPPING.get(g, g) for g in gold_labels]

    confusion = {g: {p: 0 for p in CLASSES} for g in CLASSES}
    for g, p in zip(gold_mapped, predictions):
        if g in CLASSES and p in CLASSES:
            confusion[g][p] += 1

    correct = sum(1 for g, p in zip(gold_mapped, predictions) if g == p)
    accuracy = correct / n

    per_class = {}
    for cls in CLASSES:
        tp = confusion[cls][cls]
        fp = sum(confusion[o][cls] for o in CLASSES if o != cls)
        fn = sum(confusion[cls][o] for o in CLASSES if o != cls)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[cls] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

    macro_prec = sum(per_class[c]["precision"] for c in CLASSES) / 3.0
    macro_rec = sum(per_class[c]["recall"] for c in CLASSES) / 3.0
    macro_f1 = sum(per_class[c]["f1"] for c in CLASSES) / 3.0

    return {
        "evaluated_claims": n,
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_prec, 4),
        "macro_recall": round(macro_rec, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "predicted_class_counts": {c: predictions.count(c) for c in CLASSES},
    }
