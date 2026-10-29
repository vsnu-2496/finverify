import unittest
from datetime import date
from unittest.mock import patch

import requests
from app import (
    SEC_COMPANIES,
    _classify_financial_claim,
    _retrieve_alpha_vantage_evidence,
    _retrieve_sec_evidence,
)
from research.run_openai_experiment_300 import (
    _build_evidence,
    _has_reusable_success,
    _eligible_evidence_items,
)


class EntityResolutionTests(unittest.TestCase):
    def test_resolves_verified_ford_issuer(self):
        result = _classify_financial_claim("Ford shares fell 5 percent.")

        self.assertEqual(result["claim_type"], "stock/market movement")
        self.assertEqual(result["entity"]["ticker"], "F")
        self.assertEqual(result["entity"]["cik"], "0000037996")

    def test_does_not_guess_unknown_company(self):
        result = _classify_financial_claim("Acme Widgets shares fell 5 percent.")

        self.assertEqual(result["claim_type"], "stock/market movement")
        self.assertIsNone(result["entity"])

    def test_market_research_mention_is_not_a_stock_claim(self):
        result = _classify_financial_claim(
            "The Whole Foods Market Research email is a fraudulent hoax."
        )

        self.assertNotEqual(result["claim_type"], "stock/market movement")
        self.assertIsNone(result["entity"])

    def test_share_of_economy_is_not_a_share_price_claim(self):
        result = _classify_financial_claim(
            "Revenue is the lowest it has been as a share of our economy."
        )

        self.assertNotEqual(result["claim_type"], "stock/market movement")

    def test_alpha_vantage_not_applicable_claim_is_explicit(self):
        record = {
            "claim_id": "test",
            "claim_text": "The Whole Foods Market Research email is a fraudulent hoax.",
            "claim_date": "2022-10-21",
        }

        evidence, source_errors, hard_errors, _ = _build_evidence(
            record, ("Alpha Vantage",)
        )

        self.assertEqual(evidence, [])
        self.assertFalse(hard_errors)
        self.assertEqual(source_errors[0]["status"], "not_applicable")

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"})
    @patch("research.run_openai_experiment_300._classify_financial_claim")
    @patch("research.run_openai_experiment_300._retrieve_alpha_vantage_evidence")
    def test_empty_applicable_retrieval_is_a_hard_failure(
        self, retrieve, classify
    ):
        classify.return_value = {
            "claim_type": "stock/market movement",
            "entity": {"name": "Ford Motor Co.", "ticker": "F", "cik": "0000037996"},
        }
        retrieve.return_value = ([], [])

        evidence, source_errors, hard_errors, _ = _build_evidence(
            {
                "claim_id": "test",
                "claim_text": "Ford shares fell 5 percent.",
                "claim_date": "2020-01-02",
            },
            ("Alpha Vantage",),
        )

        self.assertEqual(evidence, [])
        self.assertEqual(source_errors[0]["status"], "no_evidence")
        self.assertEqual(hard_errors, source_errors)

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"})
    @patch("research.run_openai_experiment_300._classify_financial_claim")
    @patch("research.run_openai_experiment_300._retrieve_alpha_vantage_evidence")
    def test_failed_applicable_retrieval_is_a_hard_failure(
        self, retrieve, classify
    ):
        classify.return_value = {
            "claim_type": "stock/market movement",
            "entity": {"name": "Ford Motor Co.", "ticker": "F", "cik": "0000037996"},
        }
        retrieve.return_value = (
            [],
            [{"source": "Alpha Vantage", "status": "error", "error": "request failed"}],
        )

        _, source_errors, hard_errors, _ = _build_evidence(
            {
                "claim_id": "test",
                "claim_text": "Ford shares fell 5 percent.",
                "claim_date": "2020-01-02",
            },
            ("Alpha Vantage",),
        )

        self.assertEqual(len(hard_errors), 1)
        self.assertEqual(hard_errors[0]["status"], "error")
        self.assertEqual(source_errors, hard_errors)

    @patch("research.run_openai_experiment_300._classify_financial_claim")
    @patch("research.run_openai_experiment_300._retrieve_sec_evidence")
    def test_empty_applicable_sec_retrieval_is_a_hard_failure(
        self, retrieve, classify
    ):
        classify.return_value = {
            "claim_type": "corporate operations",
            "entity": {"name": "Ford Motor Co.", "ticker": "F", "cik": "0000037996"},
        }
        retrieve.return_value = ([], [])

        evidence, source_errors, hard_errors, _ = _build_evidence(
            {
                "claim_id": "test",
                "claim_text": "Ford moved production.",
                "claim_date": "2020-01-02",
            },
            ("SEC",),
        )

        self.assertEqual(evidence, [])
        self.assertEqual(source_errors[0]["status"], "no_evidence")
        self.assertEqual(hard_errors, source_errors)

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"})
    @patch("research.run_openai_experiment_300._classify_financial_claim")
    @patch("research.run_openai_experiment_300._retrieve_alpha_vantage_evidence")
    def test_future_evidence_is_excluded_and_blocks_prediction(
        self, retrieve, classify
    ):
        classify.return_value = {
            "claim_type": "stock/market movement",
            "entity": {"name": "Ford Motor Co.", "ticker": "F", "cik": "0000037996"},
        }
        retrieve.return_value = (
            [{
                "source": "Alpha Vantage",
                "evidence_text": "Future quote",
                "evidence_date": "2021-01-02",
                "url": "https://example.invalid",
                "relevance": 0.75,
            }],
            [],
        )

        evidence, _, hard_errors, _ = _build_evidence(
            {
                "claim_id": "test",
                "claim_text": "Ford shares fell 5 percent.",
                "claim_date": "2021-01-01",
            },
            ("Alpha Vantage",),
        )

        self.assertEqual(evidence, [])
        self.assertEqual(hard_errors[0]["status"], "no_evidence")

    def test_old_prediction_without_evidence_is_not_reusable(self):
        result = {
            "status": "success",
            "evidence": [],
            "source_errors": [],
        }

        self.assertFalse(_has_reusable_success(
            result,
            ("Alpha Vantage",),
            "B2",
            {"claim_id": "test", "claim_text": "x", "claim_date": "2020-01-01"},
            "qwen2.5:3b",
        ))

    def test_resume_requires_matching_condition_claim_model_and_evidence(self):
        record = {
            "claim_id": "test",
            "claim_text": "Ford shares fell.",
            "claim_date": "2020-01-01",
        }
        evidence = {
            "source": "Alpha Vantage",
            "evidence_text": "Ford quote",
            "evidence_date": "2019-12-31",
            "temporal_status": "valid",
            "url": "https://www.alphavantage.co/query",
            "retrieved_at": "2020-01-01T00:00:00+00:00",
        }
        result = {
            **record,
            "condition": "B2",
            "provider": "ollama",
            "model": "qwen2.5:3b",
            "sources": ["Alpha Vantage"],
            "source_status": {"Alpha Vantage": "retrieved"},
            "evidence": [evidence],
            "status": "success",
        }

        self.assertTrue(_has_reusable_success(
            result, ("Alpha Vantage",), "B2", record, "qwen2.5:3b"
        ))
        self.assertFalse(_has_reusable_success(
            result, ("Alpha Vantage",), "B3", record, "qwen2.5:3b"
        ))
        self.assertFalse(_has_reusable_success(
            result, ("Alpha Vantage",), "B2", record, "other-model"
        ))
        self.assertFalse(_has_reusable_success(
            result,
            ("Alpha Vantage",),
            "B2",
            {**record, "claim_date": "2020-01-02"},
            "qwen2.5:3b",
        ))
        self.assertFalse(_has_reusable_success(
            {**result, "provider": "openai"},
            ("Alpha Vantage",),
            "B2",
            record,
            "qwen2.5:3b",
        ))

    def test_b3_resume_requires_valid_evidence_from_an_applicable_source(self):
        record = {
            "claim_id": "test",
            "claim_text": "Ford moved production.",
            "claim_date": "2020-01-01",
        }
        evidence = {
            "source": "SEC",
            "evidence_text": "Ford SEC filing evidence",
            "evidence_date": "2019-12-31",
            "temporal_status": "valid",
            "url": "https://www.sec.gov/filing",
            "retrieved_at": "2020-01-01T00:00:00+00:00",
        }
        result = {
            **record,
            "condition": "B3",
            "provider": "ollama",
            "model": "qwen2.5:3b",
            "sources": ["SEC", "Alpha Vantage"],
            "source_status": {
                "SEC": "retrieved",
                "Alpha Vantage": "not_applicable",
            },
            "evidence": [evidence],
            "status": "success",
        }

        self.assertTrue(_has_reusable_success(
            result, ("SEC", "Alpha Vantage"), "B3", record, "qwen2.5:3b"
        ))
        result["source_status"]["SEC"] = "no_evidence"
        self.assertFalse(_has_reusable_success(
            result, ("SEC", "Alpha Vantage"), "B3", record, "qwen2.5:3b"
        ))
        result["source_status"]["SEC"] = "not_applicable"
        result["source_status"]["Alpha Vantage"] = "retrieved"
        result["evidence"].append({
            **evidence,
            "source": "Alpha Vantage",
            "url": "https://www.alphavantage.co/query",
        })
        self.assertFalse(_has_reusable_success(
            result, ("SEC", "Alpha Vantage"), "B3", record, "qwen2.5:3b"
        ))

    def test_evidence_requires_claim_date_relevance_and_temporality(self):
        good = {
            "source": "SEC",
            "evidence_text": "Ford reported revenue",
            "evidence_date": "2019-12-31",
            "retrieved_at": "2020-01-01T00:00:00+00:00",
            "url": "https://www.sec.gov/filing",
        }
        missing_text = {**good, "evidence_text": ""}
        missing_date = {**good, "evidence_date": "unknown"}
        future = {**good, "evidence_date": "2020-01-02"}

        eligible = _eligible_evidence_items(
            [good.copy(), missing_text, missing_date, future],
            date(2020, 1, 1),
            ("SEC",),
        )

        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["evidence_date"], "2019-12-31")

    @patch.dict("os.environ", {}, clear=False)
    def test_sec_requires_configured_real_contact_user_agent(self):
        with patch.dict("os.environ", {"SEC_USER_AGENT": ""}):
            found, errors = _retrieve_sec_evidence(
                "Ford moved production.",
                "corporate operations",
                SEC_COMPANIES["ford"],
                date(2020, 1, 1),
            )

        self.assertEqual(found, [])
        self.assertEqual(errors[0]["status"], "error")
        self.assertIn("real contact email", errors[0]["error"])

    @patch.dict("os.environ", {"SEC_USER_AGENT": "Finance Research test@example.test"})
    @patch("app._retrieve_sec_companyfacts", return_value=[])
    @patch("app.requests.get")
    def test_sec_archive_http_403_is_reported_as_retrieval_error(
        self, get, _companyfacts
    ):
        response = requests.Response()
        response.status_code = 403
        get.return_value.raise_for_status.side_effect = requests.HTTPError(
            "403 Client Error", response=response
        )

        found, errors = _retrieve_sec_evidence(
            "Ford moved production.",
            "corporate operations",
            SEC_COMPANIES["ford"],
            date(2020, 1, 1),
        )

        self.assertEqual(found, [])
        self.assertEqual(errors[0]["status"], "error")
        self.assertIn("403", errors[0]["error"])

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"})
    @patch("app.requests.get")
    def test_alpha_vantage_rate_limit_is_not_evidence(self, get):
        response = get.return_value
        response.json.return_value = {"Note": "API call frequency limit"}
        response.status_code = 200

        evidence, errors = _retrieve_alpha_vantage_evidence(
            "Ford shares fell.", "stock/market movement",
            SEC_COMPANIES["ford"], date(2020, 1, 1),
        )

        self.assertEqual(evidence, [])
        self.assertEqual(errors[0]["status"], "error")
        self.assertIn("API call frequency limit", errors[0]["error"])

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"})
    @patch("app.requests.get")
    def test_alpha_vantage_empty_quote_is_not_evidence(self, get):
        response = get.return_value
        response.json.return_value = {"Global Quote": {}}
        response.status_code = 200

        evidence, errors = _retrieve_alpha_vantage_evidence(
            "Ford shares fell.", "stock/market movement",
            SEC_COMPANIES["ford"], date(2020, 1, 1),
        )

        self.assertEqual(evidence, [])
        self.assertEqual(errors[0]["status"], "error")
        self.assertIn("No market quote", errors[0]["error"])

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"})
    @patch("app.time.sleep")
    @patch("app.requests.get")
    def test_alpha_vantage_retries_transient_network_failure(
        self, get, sleep
    ):
        success = get.return_value
        success.json.return_value = {
            "Global Quote": {
                "07. latest trading day": "2020-01-01",
                "02. open": "10",
                "03. high": "11",
                "04. low": "9",
                "05. price": "10.5",
                "06. volume": "100",
            }
        }
        get.side_effect = [
            requests.ConnectionError("temporary reset"),
            success,
        ]

        evidence, errors = _retrieve_alpha_vantage_evidence(
            "Ford shares fell.", "stock/market movement",
            SEC_COMPANIES["ford"], date(2020, 1, 1),
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["observation_date"], "2020-01-01")
        self.assertTrue(evidence[0]["retrieved_at"])
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(2)



class VerificationPipelineAndModeTests(unittest.TestCase):
    def setUp(self):
        from app import app
        self.app = app
        self.client = app.test_client()

    @patch("app._retrieve_sec_evidence")
    @patch("app._retrieve_alpha_vantage_evidence")
    def test_retrieval_failure_produces_error_verdict_not_unverifiable(self, mock_av, mock_sec):
        # Simulate SEC hard error and no sample evidence
        mock_sec.return_value = ([], [{"source": "SEC", "status": "error", "error": "SEC EDGAR API rate limited (HTTP 429)"}])
        mock_av.return_value = ([], [{"source": "Alpha Vantage", "status": "not_applicable", "error": "Not market claim"}])

        # Test claim with unknown company to ensure no sample archive match
        response = self.client.post("/api/verify/evidence", json={
            "claims": [{"claim_id": "CLM-ERR-1", "claim_text": "NonExistentCorp reported $500M revenue."}],
            "use_demo_evidence": False,
        })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        claims = data["claims"]
        self.assertEqual(len(claims), 1)

        result = claims[0]
        # Must be separated as ERROR, never counted as UNVERIFIABLE or SUPPORTED
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["verdict"], "ERROR")
        self.assertIsNone(result["confidence"])
        self.assertEqual(result["source_mode"], "RETRIEVAL_FAILED")
        self.assertIn("Evidence retrieval failed", result["explanation"])

    def test_sample_archival_mode_is_explicitly_labelled(self):
        # Submitting Apple claim with sample fallback active
        response = self.client.post("/api/verify/evidence", json={
            "claims": [{"claim_id": "CLM-SAMP-1", "claim_text": "Apple reported total net sales of $383,285 million for fiscal year 2023."}],
            "use_demo_evidence": True,
        })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        claims = data["claims"]
        self.assertEqual(len(claims), 1)

        result = claims[0]
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source_mode"], "OFFLINE_SAMPLE_ARCHIVE")
        self.assertIn("sample archival evidence", result["retrieval_notice"].lower())
        self.assertEqual(result["confidence_type"], "MODEL_REPORTED_UNCALIBRATED")
        self.assertEqual(result["verdict"], "SUPPORTED")
        self.assertTrue(len(result["evidence"]) > 0)
        self.assertEqual(result["evidence"][0]["temporal_status"], "valid")
        self.assertTrue(result["evidence"][0]["url"].startswith("https://www.sec.gov"))

    @patch("app._call_llm_for_claim_verification")
    def test_internal_claims_error_produces_error_verdict(self, mock_llm):
        mock_llm.side_effect = RuntimeError("Ollama daemon unreachable on port 11434")

        from app import verify_internal_claims
        results = verify_internal_claims([{"claim_id": "CLM-INT-ERR", "claim_text": "Random financial assertion."}])

        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["verdict"], "ERROR")
        self.assertIsNone(res["confidence"])
        self.assertEqual(res["source_mode"], "PARAMETRIC_INTERNAL_MEMORY")


class AlphaVantageV2AndSemanticRetrievalTests(unittest.TestCase):
    def test_resolves_dow_jones_index_claim(self):
        result = _classify_financial_claim(
            "Did Trump Tweet That If 'Dow Joans' Tanked, the President Should Be Shot Out of a Cannon?"
        )
        self.assertEqual(result["claim_type"], "stock/market movement")
        self.assertIsNotNone(result["entity"])
        self.assertEqual(result["entity"]["ticker"], "DIA")
        self.assertIsNone(result["entity"]["cik"])

    def test_dow_index_not_applicable_for_sec(self):
        result = _classify_financial_claim(
            "Did Trump Tweet That If 'Dow Joans' Tanked, the President Should Be Shot Out of a Cannon?"
        )
        evidence, errors = _retrieve_sec_evidence(
            "Did Trump Tweet That If 'Dow Joans' Tanked...",
            result["claim_type"],
            result["entity"],
            date(2018, 2, 5),
        )
        self.assertEqual(evidence, [])
        self.assertEqual(errors[0]["status"], "not_applicable")
        self.assertIn("not an SEC reporting company", errors[0]["error"])

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"})
    @patch("app.requests.get")
    def test_alpha_vantage_monthly_retrieval_and_temporal_cutoff(self, mock_get):
        mock_resp = mock_get.return_value
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "Monthly Time Series": {
                "2018-02-28": {
                    "1. open": "259.95", "2. high": "262.90",
                    "3. low": "233.76", "4. close": "250.20", "5. volume": "183041900"
                },
                "2018-01-31": {
                    "1. open": "248.34", "2. high": "265.93",
                    "3. low": "247.23", "4. close": "261.44", "5. volume": "102220886"
                },
                "2017-12-29": {
                    "1. open": "242.80", "2. high": "248.00",
                    "3. low": "241.00", "4. close": "247.38", "5. volume": "85000000"
                },
            }
        }
        claim_text = "Did Trump Tweet That If 'Dow Joans' Tanked, the President Should Be Shot Out of a Cannon?"
        classification = _classify_financial_claim(claim_text)
        evidence, errors = _retrieve_alpha_vantage_evidence(
            claim_text, classification["claim_type"], classification["entity"], date(2018, 2, 5)
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["evidence_date"], "2018-01-31")
        self.assertEqual(evidence[0]["temporal_status"], "valid")
        self.assertIn("261.44", evidence[0]["evidence_text"])
        self.assertIn("DIA", evidence[0]["evidence_text"])

    def test_semantic_sec_snippet_ranking(self):
        from app import _extract_sec_snippet
        doc = (
            "Item 5.02. Board of Directors and election of officers. Nominating committee. "
            "Item 8.01. Other Events. American Airlines received $5.8 billion in financial aid under the CARES Act PSP program. "
            "Following the expiration of payroll support conditions, the company announced potential furloughs affecting 30,000 employees. "
            "Item 9.01. Financial Statements and Exhibits."
        )
        claim = "Did American Airlines Receive Billions in Federal Aid Then Lay Off 30,000 Employees?"
        snippet = _extract_sec_snippet(doc, "corporate operations", claim)
        self.assertIsNotNone(snippet)
        self.assertIn("30,000 employees", snippet.lower())
        self.assertIn("financial aid", snippet.lower())


if __name__ == "__main__":
    unittest.main()


