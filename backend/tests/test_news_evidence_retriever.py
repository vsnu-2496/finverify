"""
test_news_evidence_retriever.py

Unit tests for Phase 2:
- Provenance tracking (required provenance fields).
- Retrieval failure vs. genuine no-results distinction.
- Prospective vs. Retrospective temporal gating.
- Semantic relevance gate behavior (pure predicate matching, no truth determination).
- Deterministic candidate test set validation.
"""

import json
from pathlib import Path
import unittest

from research.canonical_mapping import (
    RETRIEVAL_SUCCESS,
    RETRIEVAL_NO_RESULTS,
    RETRIEVAL_TECHNICAL_ERROR,
    RELEVANCE_RELEVANT,
    RELEVANCE_IRRELEVANT,
)
from research.news_evidence_retriever import (
    BenchmarkNewsRetriever,
    LiveNewsRetrieverAdapter,
    check_temporal_setting,
    evaluate_news_relevance,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CANDIDATE_SET_PATH = DATA_DIR / "experiment_v3" / "candidate_test_set.json"


class TestNewsEvidenceRetriever(unittest.TestCase):

    def setUp(self):
        self.retriever = BenchmarkNewsRetriever()

    def test_provenance_fields_present_in_retrieved_items(self):
        res = self.retriever.retrieve_for_claim("finfact_002666")
        self.assertEqual(res["retrieval_status"], RETRIEVAL_SUCCESS)
        self.assertGreater(len(res["evidence_items"]), 0)

        required_keys = {
            "item_id",
            "claim_id",
            "source_name",
            "original_url",
            "publication_date",
            "retrieved_text",
            "retrieval_method",
            "retrieval_timestamp",
        }
        for item in res["evidence_items"]:
            for k in required_keys:
                self.assertIn(k, item, f"Missing provenance key {k} in item {item}")
            self.assertEqual(item["claim_id"], "finfact_002666")
            self.assertEqual(item["source_name"], "Snopes Fact Check")
            self.assertIn("snopes.com", item["original_url"])
            self.assertEqual(item["publication_date"], "2018-02-05")

    def test_distinction_between_no_results_and_technical_error(self):
        # 1. Genuine no-results (out of range ID)
        res_no_results = self.retriever.retrieve_for_claim("finfact_999999")
        self.assertEqual(res_no_results["retrieval_status"], RETRIEVAL_NO_RESULTS)
        self.assertEqual(len(res_no_results["evidence_items"]), 0)

        # 2. Technical error (invalid / missing path)
        broken_retriever = BenchmarkNewsRetriever(dataset_path=Path("non_existent_finfact.json"))
        res_error = broken_retriever.retrieve_for_claim("finfact_000001")
        self.assertEqual(res_error["retrieval_status"], RETRIEVAL_TECHNICAL_ERROR)
        self.assertIn("Failed to load benchmark dataset", res_error["error_message"])

    def test_temporal_prospective_vs_retrospective_modes(self):
        claim_date = "2018-02-05"

        # Case A: Same day (valid prospective & retrospective)
        t_same = check_temporal_setting("2018-02-05", claim_date, setting="prospective")
        self.assertTrue(t_same["is_temporally_valid"])
        self.assertFalse(t_same["is_post_claim"])

        # Case B: Post-claim date in prospective (rejected)
        t_post_pro = check_temporal_setting("2021-03-11", claim_date, setting="prospective")
        self.assertFalse(t_post_pro["is_temporally_valid"])
        self.assertTrue(t_post_pro["is_post_claim"])
        self.assertEqual(t_post_pro["reason"], "post_claim_evidence_rejected_in_prospective")

        # Case C: Post-claim date in retrospective (permitted, but flagged)
        t_post_retro = check_temporal_setting("2021-03-11", claim_date, setting="retrospective")
        self.assertTrue(t_post_retro["is_temporally_valid"])
        self.assertTrue(t_post_retro["is_post_claim"])
        self.assertEqual(t_post_retro["reason"], "post_claim_evidence_allowed_in_retrospective")

        # Case D: Missing date (strictly rejected in both)
        t_missing_pro = check_temporal_setting(None, claim_date, setting="prospective")
        self.assertFalse(t_missing_pro["is_temporally_valid"])
        self.assertEqual(t_missing_pro["reason"], "missing_date")

        t_missing_retro = check_temporal_setting(None, claim_date, setting="retrospective")
        self.assertFalse(t_missing_retro["is_temporally_valid"])
        self.assertEqual(t_missing_retro["reason"], "missing_date")

    def test_relevance_gate_rejection_rules(self):
        # 1. Boilerplate rejection
        claim = "Is COVID-19 Being Spread Through Gas Pumps?"
        bp = "Snopes is still fighting an infodemic of rumors and misinformation surrounding the COVID-19 pandemic."
        res_bp = evaluate_news_relevance(claim, bp)
        self.assertFalse(res_bp["is_relevant"])
        self.assertEqual(res_bp["reason"], "rejected_boilerplate")

        # 2. Off-modal market quote for speech claim rejection
        speech_claim = "Did Trump Tweet That If 'Dow Joans' Tanked, the President Should Be Shot Out of a Cannon?"
        market_quote = "Dow Jones Industrial Average (DIA) monthly market data: open 248.34, high 265.93, close 261.44."
        res_offmodal = evaluate_news_relevance(speech_claim, market_quote)
        self.assertFalse(res_offmodal["is_relevant"])
        self.assertEqual(res_offmodal["reason"], "off_modal_market_data_for_speech_claim")

        # 3. Entity-matching routine filing rejection
        rumor_claim = "Are Costco shutting down stores throughout the country?"
        routine_8k = "Costco Wholesale Corp Form 8-K. Item 5.02 Departure of Directors or Certain Officers."
        res_routine = evaluate_news_relevance(rumor_claim, routine_8k)
        self.assertFalse(res_routine["is_relevant"])
        self.assertEqual(res_routine["reason"], "routine_filing_irrelevant_to_consumer_rumor")

    def test_deterministic_candidate_test_set_cases(self):
        self.assertTrue(CANDIDATE_SET_PATH.exists(), f"Missing candidate set: {CANDIDATE_SET_PATH}")
        with CANDIDATE_SET_PATH.open("r", encoding="utf-8") as f:
            cset = json.load(f)

        for case in cset["test_cases"]:
            cid = case["claim_id"]
            ctext = case["claim_text"]
            cdate = case["claim_date"]
            ev_item = case["evidence_item"]

            # 1. Temporal evaluation in prospective setting
            t_pro = check_temporal_setting(ev_item["publication_date"], cdate, setting="prospective")
            self.assertEqual(
                t_pro["is_temporally_valid"],
                case["expected_temporal_prospective"],
                f"Prospective temporal mismatch in {case['test_id']}"
            )
            self.assertEqual(
                t_pro["is_post_claim"],
                case["expected_is_post_claim"],
                f"is_post_claim mismatch in {case['test_id']}"
            )

            # 2. Temporal evaluation in retrospective setting
            t_retro = check_temporal_setting(ev_item["publication_date"], cdate, setting="retrospective")
            self.assertEqual(
                t_retro["is_temporally_valid"],
                case["expected_temporal_retrospective"],
                f"Retrospective temporal mismatch in {case['test_id']}"
            )

            # 3. Semantic relevance evaluation
            rel = evaluate_news_relevance(ctext, ev_item["retrieved_text"])
            self.assertEqual(
                rel["is_relevant"],
                case["expected_relevance"],
                f"Relevance decision mismatch in {case['test_id']}: got {rel}"
            )
            if "expected_relevance_reason" in case:
                self.assertEqual(
                    rel["reason"],
                    case["expected_relevance_reason"],
                    f"Relevance reason mismatch in {case['test_id']}"
                )


if __name__ == "__main__":
    unittest.main()
