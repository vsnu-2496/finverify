"""
leakage_filter.py

Conservative, auditable verdict-leakage and uncertain-leakage filtering
for Financial News Claim Verification (Condition B4).

Safeguards:
1. Never silently rewrites text and presents it as verbatim.
2. Preserves original evidence text verbatim for provenance.
3. Classifies candidate sentences into 4 explicit categories:
   - primary_source_citation: Direct quotes, filings, press releases, official statements.
   - fact_checker_reporting: Journalistic factual reporting of events, context, or inquiries.
   - fact_checker_verdict_leakage: Explicit rating phrases, verdicts, or truth conclusions.
   - uncertain_leakage: Ambiguous editorializing, fact-checker determinations without explicit ratings.
4. Rejects all fact_checker_verdict_leakage and uncertain_leakage items with specific diagnostic reasons.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

LEAKAGE_PRIMARY_SOURCE = "primary_source_citation"
LEAKAGE_FACT_CHECKER_REPORTING = "fact_checker_reporting"
LEAKAGE_VERDICT_LEAKAGE = "fact_checker_verdict_leakage"
LEAKAGE_UNCERTAIN = "uncertain_leakage"

# Explicit rating and verdict phrases commonly used by fact-checkers (Snopes, PolitiFact, etc.)
VERDICT_PHRASES = [
    r"\bour ruling\b",
    r"\bwe rate (this|the)?\s*(claim|statement|tweet|post|rumor)?\s*(as\s*)?(true|mostly true|half true|mostly false|false|pants on fire|unproven|mixture)\b",
    r"\brating:\s*(true|mostly true|half true|mostly false|false|pants on fire|unproven|mixture)\b",
    r"\bverdict:\s*(true|mostly true|half true|mostly false|false|pants on fire|unproven|mixture)\b",
    r"\bpants on fire\b",
    r"\bmostly false\b",
    r"\bmostly true\b",
    r"\bhalf true\b",
    r"\bthis claim is (true|false|unproven|unsubstantiated|misleading|inaccurate|fake|debunked|baseless)\b",
    r"\bthe claim is (true|false|unproven|unsubstantiated|misleading|inaccurate|fake|debunked|baseless)\b",
    r"\bthis rumor is (true|false|unproven|unsubstantiated|misleading|inaccurate|fake|debunked|baseless)\b",
    r"\bthe rumor is (true|false|unproven|unsubstantiated|misleading|inaccurate|fake|debunked|baseless)\b",
    r"\bthis statement is (true|false|unproven|unsubstantiated|misleading|inaccurate|fake|debunked|baseless)\b",
    r"\bthe statement is (true|false|unproven|unsubstantiated|misleading|inaccurate|fake|debunked|baseless)\b",
    r"\bthis tweet (is|was) (fake|not real|fabricated|never posted|doctored|manipulated)\b",
    r"\bthis is (a )?(hoax|fabrication|fake news|satire|scam)\b",
    r"\bthat is (a )?(hoax|fabrication|fake news|satire|scam)\b",
    r"\b(it is|it's) (a )?(hoax|fabrication|fake news|satire|scam)\b",
    r"\bthis (post|image|video|quote) (is|was) (fake|doctored|fabricated|manipulated)\b",
    r"\bwe found this claim to be (true|false|misleading|unproven)\b",
    r"\b(this|the)\s+(meme|narrative|story|headline|post|graphic|video|photo|image|quote|article)\s+(is|was)\s+(largely|mostly|partially|completely|entirely)?\s*(true|false|fake|real|accurate|inaccurate|debunked)\b",
    r"\b(it\s+is|it's)\s+(true|false|unproven|accurate|inaccurate)\s+that\b",
    r"\bbecause\s+it('s|\s+is)\s+(not\s+real|fake|fabricated)\b",
    r"\b(is|was|are|were)\s+not\s+real\b",
    r"\b(the|this)?\s*(fake|fabricated|doctored|manipulated)\s+(photo|voucher|post|offer|claim|video|image|letter|document|tweet|check|coupon)\b",
]

# Editorial truth conclusions and debunking statements
EDITORIAL_CONCLUSION_PATTERNS = [
    r"\b(in fact|in reality),?\s*(this|the)\s*(tweet|claim|quote|statement|story)\s*(is|was|never)\b",
    r"\bthere is (no|little) (credible\s+)?evidence (that|to support)\b",
    r"\bwe found (no|little) (credible\s+)?evidence (that|to support)\b",
    r"\bnot\s+aware\s+of\s+any\s+(credible|factual|official)\s+(reports|evidence)\b",
    r"\bwe\s+found\s+no\s+(credible\s+)?(record|reports)\b",
    r"\bthere\s+is\s+no\s+(credible\s+)?(record|reports)\b",
    r"\bhas been debunked\b",
    r"\bwas debunked\b",
    r"\bto debunk\b",
    r"\bdebunking\b",
    r"\bcorrects the record\b",
    r"\bcontrary to (the|these|popular) claims?\b",
]

# Uncertain / ambiguous leakage: editorial evaluations where fact-checkers assert findings
UNCERTAIN_LEAKAGE_PATTERNS = [
    r"\b(snopes|politifact|factcheck\.org|lead stories|reuters fact check|ap fact check)\s*(found|determined|confirmed|concluded|verified|noted|rated)\b",
    r"\bour (investigation|research|fact[ -]check|analysis)\s*(found|shows|determined|reveals)\b",
    r"\bwe (investigated|reached out to|contacted|reviewed|searched)\b",
    r"\bno credible source (reports|supports|states|indicates)\b",
    r"\bno record exists?\b",
    r"\bno record of (such a|any such|this)\b",
]

# Primary source patterns (official filings, direct quotes, press releases)
PRIMARY_SOURCE_PATTERNS = [
    r"\b(sec filing|form 10-k|form 10-q|form 8-k|edgar|press release|spokesperson said|spokeswoman said|stated in a statement|announced in a statement)\b",
    r"\b(according to data from|official statistics|bureau of labor statistics|according to (the )?federal reserve|federal reserve reported|federal reserve announced|u\.s\. treasury data)\b",
    r"^[“\"'].+[”\"']$",  # direct quote block
]


def classify_sentence(sentence: str) -> Dict[str, Any]:
    """
    Classifies an individual evidence sentence for verdict leakage.
    Returns:
    {
        "classification": str,
        "is_accepted": bool,
        "rejection_reason": Optional[str],
        "matched_patterns": List[str],
        "original_text": str
    }
    """
    s_clean = sentence.strip()
    s_lower = s_clean.lower()

    # Check 1: Explicit verdict / rating phrases -> definite leakage
    matched_verdicts = []
    for pat in VERDICT_PHRASES:
        m = re.search(pat, s_lower, re.IGNORECASE)
        if m:
            matched_verdicts.append(m.group(0))

    if matched_verdicts:
        return {
            "classification": LEAKAGE_VERDICT_LEAKAGE,
            "is_accepted": False,
            "rejection_reason": "verdict_rating_phrase_detected",
            "matched_patterns": matched_verdicts,
            "original_text": s_clean,
        }

    # Check 2: Editorial truth conclusions -> definite leakage
    matched_editorial = []
    for pat in EDITORIAL_CONCLUSION_PATTERNS:
        m = re.search(pat, s_lower, re.IGNORECASE)
        if m:
            matched_editorial.append(m.group(0))

    if matched_editorial:
        return {
            "classification": LEAKAGE_VERDICT_LEAKAGE,
            "is_accepted": False,
            "rejection_reason": "editorial_truth_conclusion_detected",
            "matched_patterns": matched_editorial,
            "original_text": s_clean,
        }

    # Check 3: Uncertain leakage patterns -> conservatively reject
    matched_uncertain = []
    for pat in UNCERTAIN_LEAKAGE_PATTERNS:
        m = re.search(pat, s_lower, re.IGNORECASE)
        if m:
            matched_uncertain.append(m.group(0))

    if matched_uncertain:
        return {
            "classification": LEAKAGE_UNCERTAIN,
            "is_accepted": False,
            "rejection_reason": "uncertain_verdict_leakage_flagged",
            "matched_patterns": matched_uncertain,
            "original_text": s_clean,
        }

    # Check 4: Check if it is a primary source citation
    matched_primary = []
    for pat in PRIMARY_SOURCE_PATTERNS:
        m = re.search(pat, s_lower, re.IGNORECASE)
        if m:
            matched_primary.append(m.group(0))

    if matched_primary or (s_clean.startswith(('"', "“")) and s_clean.endswith(('"', "”"))):
        return {
            "classification": LEAKAGE_PRIMARY_SOURCE,
            "is_accepted": True,
            "rejection_reason": None,
            "matched_patterns": matched_primary,
            "original_text": s_clean,
        }

    # Otherwise: Journalistic factual reporting
    return {
        "classification": LEAKAGE_FACT_CHECKER_REPORTING,
        "is_accepted": True,
        "rejection_reason": None,
        "matched_patterns": [],
        "original_text": s_clean,
    }


def filter_evidence_items(
    evidence_items: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Filters a list of retrieved evidence items, separating them into
    accepted items and rejected leakage items.
    
    Preserves all original fields verbatim without rewriting text.
    Augments items with audit fields:
    - leakage_classification
    - is_leakage_accepted
    - leakage_rejection_reason
    - leakage_matched_patterns
    """
    accepted = []
    rejected = []

    for item in evidence_items:
        text = item.get("retrieved_text", "")
        res = classify_sentence(text)

        audited_item = dict(item)
        audited_item["leakage_classification"] = res["classification"]
        audited_item["is_leakage_accepted"] = res["is_accepted"]
        audited_item["leakage_rejection_reason"] = res["rejection_reason"]
        audited_item["leakage_matched_patterns"] = res["matched_patterns"]

        if res["is_accepted"]:
            accepted.append(audited_item)
        else:
            rejected.append(audited_item)

    return accepted, rejected
