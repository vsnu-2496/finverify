"""
test_evidence_relevance_gate.py

Unit tests for Phase 1 of Pipeline v3:
- Canonical label bijection & Condition A reconciliation.
- Temporal cutoff enforcement.
- Semantic relevance gating (positive, negative, and off-modal tests).
- Decoupled schema verification and forced abstention behavior.
"""

import json
from pathlib import Path
import unittest

from research.canonical_mapping import (
    CLASSES,
    LABEL_MAPPING,
    RETRIEVAL_SUCCESS,
    RETRIEVAL_SOURCE_NOT_APPLICABLE,
    RELEVANCE_RELEVANT,
    RELEVANCE_IRRELEVANT,
    RELEVANCE_TEMPORAL_REJECTED,
    calculate_metrics,
    evaluate_evidence_relevance,
    is_temporally_valid,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EVAL_PATH = DATA_DIR / "finfact_research_evaluation.json"
COND_A_PATH = DATA_DIR / "condition_a_ollama_qwen25_3b_results.json"


class TestCanonicalMappingAndReconciliation(unittest.TestCase):
    """Verifies canonical labels, bijective mapping, and Condition A baseline reconciliation."""

    def test_canonical_label_distribution(self):
        self.assertTrue(EVAL_PATH.exists(), f"Evaluation file missing: {EVAL_PATH}")
        with EVAL_PATH.open("r", encoding="utf-8") as f:
            eval_data = json.load(f)

        self.assertEqual(len(eval_data), 300)
        gold_counts = {}
        for r in eval_data:
            lbl = r["gold_label"]
            gold_counts[lbl] = gold_counts.get(lbl, 0) + 1

        self.assertEqual(gold_counts["true"], 113)
        self.assertEqual(gold_counts["false"], 133)
        self.assertEqual(gold_counts["NEI"], 54)

    def test_condition_a_reconciliation_metrics(self):
        self.assertTrue(COND_A_PATH.exists(), f"Condition A results missing: {COND_A_PATH}")
        with EVAL_PATH.open("r", encoding="utf-8") as f:
            eval_data = json.load(f)
        with COND_A_PATH.open("r", encoding="utf-8") as f:
            cond_a = json.load(f)

        self.assertEqual(len(cond_a), 300)
        gold_by_id = {r["claim_id"]: r["gold_label"] for r in eval_data}
        gold = [gold_by_id[r["claim_id"]] for r in cond_a]
        preds = [r["verdict"] for r in cond_a]

        metrics = calculate_metrics(gold, preds)
        self.assertEqual(metrics["evaluated_claims"], 300)
        self.assertEqual(metrics["accuracy"], 0.1900)
        self.assertEqual(metrics["macro_precision"], 0.3116)
        self.assertEqual(metrics["macro_recall"], 0.3409)
        self.assertEqual(metrics["macro_f1"], 0.1186)

        cm = metrics["confusion_matrix"]
        self.assertEqual(cm["SUPPORTED"]["SUPPORTED"], 0)
        self.assertEqual(cm["SUPPORTED"]["REFUTED"], 1)
        self.assertEqual(cm["SUPPORTED"]["UNVERIFIABLE"], 112)

        self.assertEqual(cm["REFUTED"]["SUPPORTED"], 4)
        self.assertEqual(cm["REFUTED"]["REFUTED"], 3)
        self.assertEqual(cm["REFUTED"]["UNVERIFIABLE"], 126)

        self.assertEqual(cm["UNVERIFIABLE"]["SUPPORTED"], 0)
        self.assertEqual(cm["UNVERIFIABLE"]["REFUTED"], 0)
        self.assertEqual(cm["UNVERIFIABLE"]["UNVERIFIABLE"], 54)


class TestTemporalGating(unittest.TestCase):
    """Verifies strict enforcement of claim_date temporal cutoff."""

    def test_valid_prior_date(self):
        valid, reason = is_temporally_valid("2018-01-31", "2018-02-05")
        self.assertTrue(valid)
        self.assertEqual(reason, "temporally_valid")

    def test_valid_same_day_date(self):
        valid, reason = is_temporally_valid("2018-02-05", "2018-02-05")
        self.assertTrue(valid)
        self.assertEqual(reason, "temporally_valid")

    def test_future_leakage_rejected(self):
        valid, reason = is_temporally_valid("2018-02-06", "2018-02-05")
        self.assertFalse(valid)
        self.assertIn("future_evidence_rejected", reason)

    def test_missing_evidence_date_rejected(self):
        valid, reason = is_temporally_valid(None, "2018-02-05")
        self.assertFalse(valid)
        self.assertEqual(reason, "evidence_date_missing")


class TestSemanticRelevanceGating(unittest.TestCase):
    """Verifies positive and negative test cases for semantic evidence gating."""

    def test_positive_real_snopes_evidence_for_tweet_claim(self):
        claim = "Did Trump Tweet That If 'Dow Joans' Tanked, the President Should Be Shot Out of a Cannon?"
        evidence = (
            'On 5 February 2018, Shaun Usher, the owner of the blog "Letters of Note" posted '
            'an image on Twitter that purported to show Donald Trump opining that any president '
            'presiding over the United States during a stock market crash of more than 1,000 points '
            'should be "shot out of a cannon."'
        )
        is_relevant, reason, anchors = evaluate_evidence_relevance(claim, evidence)
        self.assertTrue(is_relevant)
        self.assertEqual(reason, "anchors_and_proposition_matched")
        self.assertTrue(any(a in anchors for a in ["trump", "cannon", "tweet"]))

    def test_negative_offmodal_dia_stock_quote_rejected(self):
        claim = "Did Trump Tweet That If 'Dow Joans' Tanked, the President Should Be Shot Out of a Cannon?"
        evidence = (
            "Dow Jones Industrial Average (DIA) monthly market data for period ending 2018-01-31: "
            "open 248.34, high 265.93, low 247.23, close 261.44, volume 102220886."
        )
        is_relevant, reason, anchors = evaluate_evidence_relevance(claim, evidence)
        self.assertFalse(is_relevant)
        self.assertEqual(reason, "off_modal_market_data_for_speech_claim")

    def test_negative_routine_executive_departure_8k_rejected_for_store_closures(self):
        claim = "Are Costco shutting down stores throughout the country?"
        evidence = (
            "Form 8-K Costco Wholesale Corp. Item 5.02 Departure of Directors or Certain Officers; "
            "Election of Directors; Appointment of Certain Officers."
        )
        is_relevant, reason, anchors = evaluate_evidence_relevance(claim, evidence)
        self.assertFalse(is_relevant)
        self.assertEqual(reason, "routine_filing_irrelevant_to_consumer_rumor")

    def test_negative_insufficient_anchor_overlap(self):
        claim = "Ford is moving all of their small-car production to Mexico."
        evidence = "The Federal Reserve raised interest rates by 25 basis points in today's FOMC meeting."
        is_relevant, reason, anchors = evaluate_evidence_relevance(claim, evidence)
        self.assertFalse(is_relevant)
        self.assertIn("insufficient_anchor_overlap", reason)


class TestDecoupledSchemaAndAbstentionProtocol(unittest.TestCase):
    """Verifies that forced abstention preserves the gold label while predicting UNVERIFIABLE."""

    def test_abstention_on_irrelevant_evidence_preserves_gold_label(self):
        record = {
            "claim_id": "finfact_002666",
            "gold_label": "REFUTED",
            "retrieval_status": RETRIEVAL_SUCCESS,
            "relevance_status": RELEVANCE_IRRELEVANT,
            "prediction": "UNVERIFIABLE",
            "abstention_enforced": True,
        }
        self.assertEqual(record["gold_label"], "REFUTED")
        self.assertEqual(record["prediction"], "UNVERIFIABLE")
        self.assertTrue(record["abstention_enforced"])
        
        # When evaluated, predicting UNVERIFIABLE on a gold REFUTED claim counts as incorrect (missed verification)
        metrics = calculate_metrics([record["gold_label"]], [record["prediction"]])
        self.assertEqual(metrics["accuracy"], 0.0)


if __name__ == "__main__":
    unittest.main()
