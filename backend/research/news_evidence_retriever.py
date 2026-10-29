"""
news_evidence_retriever.py

Component for news-evidence retrieval, provenance tracking, temporal gating,
and semantic relevance assessment for Financial News Claim Verification.

Supports:
- BenchmarkNewsRetriever: Authentic fact-checking & news evidence from benchmark corpus.
- LiveNewsRetrieverAdapter: Configurable interface for live web search.
- Decoupled Temporal Modes: Prospective (pre-claim cutoff) vs. Retrospective (post-claim allowed with flag).
- Independent Semantic Relevance Gate: Pure predicate-anchor and topic validation without verdict inference.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from research.canonical_mapping import (
    RETRIEVAL_SUCCESS,
    RETRIEVAL_NO_RESULTS,
    RETRIEVAL_TECHNICAL_ERROR,
    RELEVANCE_RELEVANT,
    RELEVANCE_IRRELEVANT,
    RELEVANCE_TEMPORAL_REJECTED,
    parse_iso_date,
)

BOILERPLATE_PATTERNS = [
    "snopes is still fighting an infodemic",
    "become a founding member",
    "submit any questionable rumors",
    "follow the cdc or who for guidance",
    "all rights reserved",
    "click here to subscribe",
]


class BenchmarkNewsRetriever:
    """Retrieves authentic evidence sentences and source metadata from finfact.json."""

    def __init__(self, dataset_path: Optional[Path] = None):
        if dataset_path is None:
            # Default to finfact.json in project root
            dataset_path = Path(__file__).resolve().parents[2] / "finfact.json"
        self.dataset_path = Path(dataset_path)
        self._cache: Optional[List[Dict[str, Any]]] = None

    def _ensure_loaded(self):
        if self._cache is None:
            if not self.dataset_path.exists():
                raise FileNotFoundError(f"Benchmark file not found: {self.dataset_path}")
            with self.dataset_path.open("r", encoding="utf-8") as f:
                self._cache = json.load(f)

    def retrieve_for_claim(self, claim_id: str) -> Dict[str, Any]:
        """
        Retrieves authentic evidence for the given claim ID (finfact_XXXXXX).
        Returns standardized provenance payload.
        """
        try:
            self._ensure_loaded()
        except Exception as ex:
            return {
                "claim_id": claim_id,
                "retrieval_status": RETRIEVAL_TECHNICAL_ERROR,
                "error_message": f"Failed to load benchmark dataset: {str(ex)}",
                "retrieval_method": "benchmark_archive",
                "evidence_items": [],
            }

        try:
            # finfact_000001 -> row 0 in finfact.json
            idx = int(claim_id.split("_")[1]) - 1
            if idx < 0 or idx >= len(self._cache):
                return {
                    "claim_id": claim_id,
                    "retrieval_status": RETRIEVAL_NO_RESULTS,
                    "error_message": f"Claim index {idx} out of range (0-{len(self._cache)-1})",
                    "retrieval_method": "benchmark_archive",
                    "evidence_items": [],
                }

            row = self._cache[idx]
        except Exception as ex:
            return {
                "claim_id": claim_id,
                "retrieval_status": RETRIEVAL_TECHNICAL_ERROR,
                "error_message": f"Index parse error: {str(ex)}",
                "retrieval_method": "benchmark_archive",
                "evidence_items": [],
            }

        raw_evidence = row.get("evidence", [])
        raw_url = row.get("url")
        raw_posted = row.get("posted")

        # Determine source domain
        source_name = "Unknown"
        if raw_url:
            if "snopes.com" in raw_url:
                source_name = "Snopes Fact Check"
            elif "politifact.com" in raw_url:
                source_name = "PolitiFact"
            else:
                source_name = raw_url.split("//")[-1].split("/")[0]

        # Normalize publication date (MM/DD/YYYY -> YYYY-MM-DD)
        norm_date = None
        if raw_posted:
            dt = parse_iso_date(raw_posted)
            if dt:
                norm_date = dt.strftime("%Y-%m-%d")

        evidence_items = []
        if isinstance(raw_evidence, list):
            for i, ev in enumerate(raw_evidence):
                sentence = ev.get("sentence", "").strip() if isinstance(ev, dict) else str(ev).strip()
                if not sentence:
                    continue
                hrefs = ev.get("hrefs", []) if isinstance(ev, dict) else []
                citation_url = hrefs[0] if hrefs else raw_url

                evidence_items.append({
                    "item_id": f"{claim_id}_ev_{i+1}",
                    "claim_id": claim_id,
                    "source_name": source_name,
                    "article_url": raw_url,
                    "original_url": raw_url,
                    "citation_url": citation_url,
                    "publication_date": norm_date,
                    "retrieved_text": sentence,
                    "retrieval_method": "benchmark_archive",
                    "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                    "reference_hrefs": hrefs,
                })

        if not evidence_items:
            return {
                "claim_id": claim_id,
                "retrieval_status": RETRIEVAL_NO_RESULTS,
                "error_message": None,
                "retrieval_method": "benchmark_archive",
                "evidence_items": [],
            }

        return {
            "claim_id": claim_id,
            "retrieval_status": RETRIEVAL_SUCCESS,
            "error_message": None,
            "retrieval_method": "benchmark_archive",
            "evidence_items": evidence_items,
        }


class LiveNewsRetrieverAdapter:
    """Configurable adapter for live news search APIs with failure isolation."""

    def __init__(self, api_key: Optional[str] = None, enabled: bool = False):
        self.api_key = api_key
        self.enabled = enabled

    def retrieve_for_claim(self, claim_id: str, query: str) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "claim_id": claim_id,
                "retrieval_status": RETRIEVAL_TECHNICAL_ERROR,
                "error_message": "LiveNewsRetrieverAdapter is disabled in Phase 2.",
                "retrieval_method": "live_search",
                "evidence_items": [],
            }
        # Placeholder for approved live API calls
        return {
            "claim_id": claim_id,
            "retrieval_status": RETRIEVAL_NO_RESULTS,
            "error_message": None,
            "retrieval_method": "live_search",
            "evidence_items": [],
        }


def check_temporal_setting(
    evidence_date: Optional[str],
    claim_date: Optional[str],
    setting: str = "prospective"
) -> Dict[str, Any]:
    """
    Decouples temporal validation modes:
    - prospective: strictly rejects evidence_date > claim_date and missing dates.
    - retrospective: permits post-claim investigations, explicitly flagging is_post_claim.
    """
    if not claim_date:
        return {
            "is_temporally_valid": False,
            "reason": "claim_date_missing",
            "is_post_claim": False,
            "temporal_setting": setting,
        }
    if not evidence_date:
        return {
            "is_temporally_valid": False,
            "reason": "missing_date",
            "is_post_claim": False,
            "temporal_setting": setting,
        }

    c_dt = parse_iso_date(claim_date)
    e_dt = parse_iso_date(evidence_date)

    if not c_dt or not e_dt:
        return {
            "is_temporally_valid": False,
            "reason": "invalid_date_format",
            "is_post_claim": False,
            "temporal_setting": setting,
        }

    is_post = e_dt.date() > c_dt.date()

    if setting == "prospective":
        if is_post:
            return {
                "is_temporally_valid": False,
                "reason": "post_claim_evidence_rejected_in_prospective",
                "is_post_claim": True,
                "temporal_setting": setting,
            }
        return {
            "is_temporally_valid": True,
            "reason": "temporally_valid_prospective",
            "is_post_claim": False,
            "temporal_setting": setting,
        }
    elif setting == "retrospective":
        return {
            "is_temporally_valid": True,
            "reason": "post_claim_evidence_allowed_in_retrospective" if is_post else "pre_claim_evidence",
            "is_post_claim": is_post,
            "temporal_setting": setting,
        }
    else:
        raise ValueError(f"Unknown temporal setting: {setting}")


def evaluate_news_relevance(
    claim_text: str,
    evidence_text: str,
    source_type: str = "news"
) -> Dict[str, Any]:
    """
    Evaluates semantic and propositional relevance of evidence to claim.
    DOES NOT infer truth or falsehood of the claim.
    """
    claim_lower = claim_text.lower()
    ev_lower = evidence_text.lower()

    # Rule 1: Reject site boilerplate
    for bp in BOILERPLATE_PATTERNS:
        if bp in ev_lower:
            return {
                "is_relevant": False,
                "relevance_status": RELEVANCE_IRRELEVANT,
                "reason": "rejected_boilerplate",
                "matched_anchors": [],
            }

    # Rule 2: Reject off-modal numerical tables for speech/tweet claims
    is_speech_claim = any(kw in claim_lower for kw in ["tweet", "tweeted", "said", "quote", "claimed", "stated", "shot out of a cannon"])
    is_market_data = any(kw in ev_lower for kw in ["monthly market data", "open ", "high ", "close ", "volume ", "global quote"])
    if is_speech_claim and is_market_data and not any(kw in ev_lower for kw in ["tweet", "twitter", "post", "statement", "transcript"]):
        return {
            "is_relevant": False,
            "relevance_status": RELEVANCE_IRRELEVANT,
            "reason": "off_modal_market_data_for_speech_claim",
            "matched_anchors": [],
        }

    # Rule 3: Reject routine corporate 8-Ks for retail rumors
    is_rumor_claim = any(kw in claim_lower for kw in ["shutting down stores", "closing down", "boycott", "scam"])
    is_routine_8k = "departure of directors or certain officers" in ev_lower or "unregistered sales of equity" in ev_lower
    if is_rumor_claim and is_routine_8k and not any(kw in ev_lower for kw in ["close", "closing", "shutdown", "store", "locations"]):
        return {
            "is_relevant": False,
            "relevance_status": RELEVANCE_IRRELEVANT,
            "reason": "routine_filing_irrelevant_to_consumer_rumor",
            "matched_anchors": [],
        }

    # Rule 4: Extract meaningful terms (> 3 chars, not stopwords)
    stopwords = {"that", "this", "what", "with", "from", "have", "were", "been", "their", "there", "about", "would", "could", "should"}
    claim_tokens = [w.strip("?,.:;\"'()[]") for w in claim_lower.split() if len(w) > 3 and w not in stopwords]

    matched_anchors = [w for w in claim_tokens if w in ev_lower]

    # Must match at least 2 distinct anchor terms to address the predicate/event
    if len(matched_anchors) < 2:
        return {
            "is_relevant": False,
            "relevance_status": RELEVANCE_IRRELEVANT,
            "reason": f"insufficient_predicate_anchors: {matched_anchors}",
            "matched_anchors": matched_anchors,
        }

    return {
        "is_relevant": True,
        "relevance_status": RELEVANCE_RELEVANT,
        "reason": "proposition_and_predicate_anchors_matched",
        "matched_anchors": matched_anchors,
    }
