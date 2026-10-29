"""
test_condition_b4_runner.py

Unit tests for Condition B4 runner, leakage filter, and dry-run accounting.
"""

from pathlib import Path
import json
import tempfile
import unittest

from research.canonical_mapping import (
    CLASSES,
    STATUS_GROUNDED_SUCCESS,
    STATUS_NO_RELEVANT_EVIDENCE,
    STATUS_RETRIEVAL_ERROR,
    STATUS_INFERENCE_ERROR,
    calculate_metrics,
    verify_manifest,
)
from research.leakage_filter import (
    classify_sentence,
    filter_evidence_items,
    LEAKAGE_PRIMARY_SOURCE,
    LEAKAGE_FACT_CHECKER_REPORTING,
    LEAKAGE_VERDICT_LEAKAGE,
    LEAKAGE_UNCERTAIN,
)
from research.run_condition_b4 import (
    build_b4_prompt,
    parse_and_validate_llm_response,
    request_ollama_inference,
    save_progress_atomic,
    process_claim_evidence,
    run_pipeline,
    EXPERIMENTAL_CONDITION_LABEL,
)
from research.news_evidence_retriever import BenchmarkNewsRetriever
from research.evaluate_v3_results import resolve_results_path


class TestManifestVerification(unittest.TestCase):
    def test_pre_run_manifest_passes_on_repo(self):
        ok, report = verify_manifest()
        self.assertTrue(ok)
        self.assertEqual(len(report), 7)
        for path, status in report.items():
            self.assertTrue(status.startswith("OK"), f"Failed for {path}: {status}")

    def test_manifest_fails_on_missing_or_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            man_file = tmppath / "test_manifest.sha256"
            man_file.write_text("0000000000000000000000000000000000000000000000000000000000000000  missing.json\n")
            ok, rep = verify_manifest(manifest_path=man_file, root_dir=tmppath)
            self.assertFalse(ok)
            self.assertIn("missing.json", rep)
            self.assertTrue(rep["missing.json"].startswith("MISSING"))


class TestLeakageFilter(unittest.TestCase):
    def test_verdict_leakage_rejection(self):
        # Explicit ruling
        res1 = classify_sentence("Our ruling: We rate this claim False.")
        self.assertEqual(res1["classification"], LEAKAGE_VERDICT_LEAKAGE)
        self.assertFalse(res1["is_accepted"])
        self.assertEqual(res1["rejection_reason"], "verdict_rating_phrase_detected")

        # Explicit 'pants on fire'
        res2 = classify_sentence("PolitiFact gives this a pants on fire rating.")
        self.assertEqual(res2["classification"], LEAKAGE_VERDICT_LEAKAGE)
        self.assertFalse(res2["is_accepted"])

        # Truth conclusion: fake tweet
        res3 = classify_sentence("In reality, this tweet was not real and Trump never posted it.")
        self.assertEqual(res3["classification"], LEAKAGE_VERDICT_LEAKAGE)
        self.assertFalse(res3["is_accepted"])

    def test_uncertain_leakage_rejection(self):
        # Fact-checker finding / investigation without explicit rating
        res = classify_sentence("Snopes found that the store was operating under normal business hours.")
        self.assertEqual(res["classification"], LEAKAGE_UNCERTAIN)
        self.assertFalse(res["is_accepted"])
        self.assertEqual(res["rejection_reason"], "uncertain_verdict_leakage_flagged")

    def test_primary_source_citation_accepted(self):
        # Direct quote from SEC or official entity
        res = classify_sentence("According to data from the Bureau of Labor Statistics, the unemployment rate was 3.8%.")
        self.assertEqual(res["classification"], LEAKAGE_PRIMARY_SOURCE)
        self.assertTrue(res["is_accepted"])
        self.assertIsNone(res["rejection_reason"])

    def test_factual_reporting_accepted(self):
        # Pure journalistic context
        res = classify_sentence("The Dow Jones Industrial Average dropped 800 points following the Federal Reserve rate hike.")
        self.assertEqual(res["classification"], LEAKAGE_FACT_CHECKER_REPORTING)
        self.assertTrue(res["is_accepted"])
        self.assertIsNone(res["rejection_reason"])

    def test_filter_evidence_items_preserves_verbatim_text(self):
        raw_items = [
            {"retrieved_text": "The Federal Reserve raised interest rates by 25 basis points in March."},
            {"retrieved_text": "Our ruling: This claim is mostly false."},
            {"retrieved_text": "Snopes determined no record exists of this statement."},
        ]
        accepted, rejected = filter_evidence_items(raw_items)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 2)

        # Verbatim preservation check
        self.assertEqual(accepted[0]["retrieved_text"], raw_items[0]["retrieved_text"])
        self.assertEqual(rejected[0]["retrieved_text"], raw_items[1]["retrieved_text"])
        self.assertEqual(rejected[1]["retrieved_text"], raw_items[2]["retrieved_text"])

    def test_semantic_verdict_leakage_regression(self):
        # Identified examples from Phase B audit
        leakage_cases = [
            "The military did not spend $1 billion on this 'new vehicle' because it's not real.",
            "This meme is largely true, though the length of the GGW varies, as the project itself is far from being completed.",
            "The fake voucher offer for Chick-fil-A appeared on facebook.com/ChickFans as well as other pages.",
            "It is true that President Trump filed a letter on Inauguration Day, 20 January 2017.",
            "Reuters first reported on the fake photo with the lobsters on Dec. 5.",
            "We're not aware of any credible reports of COVID-19 being spread via gas pump handles.",
        ]
        for sentence in leakage_cases:
            res = classify_sentence(sentence)
            self.assertFalse(
                res["is_accepted"],
                f"Expected semantic leakage to be rejected, but was accepted: {sentence}",
            )
            self.assertEqual(res["classification"], LEAKAGE_VERDICT_LEAKAGE)

    def test_neutral_financial_reporting_not_rejected(self):
        # Neutral economic/corporate facts must be preserved
        neutral_cases = [
            "Apple Inc. reported fourth quarter revenue of $89.5 billion, down 1 percent year-over-year.",
            "The Federal Reserve increased the benchmark interest rate by 25 basis points in March.",
            "Costco Wholesale Corp. operated 828 warehouses globally as of fiscal year 2022.",
            "Total net sales grew by 4.2 percent compared to the prior fiscal year.",
            "Microsoft completed its acquisition of Nuance Communications following regulatory approval.",
        ]
        for sentence in neutral_cases:
            res = classify_sentence(sentence)
            self.assertTrue(
                res["is_accepted"],
                f"Expected neutral sentence to be accepted, but was rejected: {sentence} (reason: {res.get('rejection_reason')})",
            )
            self.assertIn(res["classification"], [LEAKAGE_FACT_CHECKER_REPORTING, LEAKAGE_PRIMARY_SOURCE])


class TestConditionB4Runner(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.sample_path = self.project_root / "backend" / "data" / "finfact_research_sample.json"

    def test_prompt_builder_format(self):
        prompt = build_b4_prompt(
            claim_text="Amazon is shutting down all retail stores.",
            evidence_items=[{
                "source_name": "Reuters",
                "publication_date": "2022-03-02",
                "retrieved_text": "Amazon announced it is closing 68 physical retail stores."
            }]
        )
        self.assertIn("Amazon is shutting down all retail stores.", prompt)
        self.assertIn("Amazon announced it is closing 68 physical retail stores.", prompt)
        self.assertIn("SUPPORTED", prompt)
        self.assertIn("REFUTED", prompt)
        self.assertIn("UNVERIFIABLE", prompt)

    def test_dry_run_accounting_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            out_file = tmppath / "dry_run_results.json"
            audit_file = tmppath / "dry_run_audit.json"

            summary = run_pipeline(
                sample_path=self.sample_path,
                output_path=out_file,
                audit_path=audit_file,
                dry_run=True,
                temporal_setting="retrospective",
            )

            # Check total claims and 4-tier invariant
            self.assertEqual(summary["total_claims"], 300)
            status_counts = summary["status_accounting"]
            total = sum(status_counts.values())
            self.assertEqual(total, 300)
            self.assertEqual(status_counts[STATUS_RETRIEVAL_ERROR], 0)
            self.assertEqual(status_counts[STATUS_INFERENCE_ERROR], 0)

            # Grounded success and abstention non-zero and sum to 300
            self.assertEqual(status_counts[STATUS_GROUNDED_SUCCESS], 232)
            self.assertEqual(status_counts[STATUS_NO_RELEVANT_EVIDENCE], 68)

            # Coverage rates
            rates = summary["coverage_metrics"]
            self.assertEqual(rates["evidence_coverage_rate"], 0.7733)
            self.assertEqual(rates["abstention_rate"], 0.2267)

            # Verify experimental condition label
            self.assertEqual(summary["experimental_condition"], EXPERIMENTAL_CONDITION_LABEL)


class TestEvaluatorPathResolution(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.backend_dir = self.project_root / "backend"

    def test_resolve_from_backend_cwd_relative(self):
        # Simulates running from backend/ with .\data\experiment_v3\condition_b4_dry_run_results.json
        res = resolve_results_path(
            r".\data\experiment_v3\condition_b4_dry_run_results.json",
            project_root=self.project_root,
            cwd=self.backend_dir,
        )
        self.assertTrue(res.exists())
        self.assertEqual(res.name, "condition_b4_dry_run_results.json")

    def test_resolve_from_project_root_relative(self):
        # Simulates running from project root with backend/data/experiment_v3/...
        res = resolve_results_path(
            "backend/data/experiment_v3/condition_b4_dry_run_results.json",
            project_root=self.project_root,
            cwd=self.project_root,
        )
        self.assertTrue(res.exists())
        self.assertEqual(res.name, "condition_b4_dry_run_results.json")

    def test_resolve_default_arg_from_backend_cwd(self):
        # Default argument is 'backend/data/experiment_v3/condition_b4_dry_run_results.json'
        # Even when CWD is backend/, it should resolve via project_root
        res = resolve_results_path(
            "backend/data/experiment_v3/condition_b4_dry_run_results.json",
            project_root=self.project_root,
            cwd=self.backend_dir,
        )
        self.assertTrue(res.exists())
        self.assertEqual(res.name, "condition_b4_dry_run_results.json")

    def test_resolve_absolute_path(self):
        target = self.backend_dir / "data" / "experiment_v3" / "condition_b4_dry_run_results.json"
        res = resolve_results_path(str(target), project_root=self.project_root)
        self.assertEqual(res.resolve(), target.resolve())

    def test_resolve_missing_file_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            resolve_results_path(
                "non_existent_results_file.json",
                project_root=self.project_root,
                cwd=self.backend_dir,
            )
        err_msg = str(ctx.exception)
        self.assertIn("non_existent_results_file.json", err_msg)
        self.assertIn("Attempted relative to CWD", err_msg)
        self.assertIn("Attempted relative to project root", err_msg)


class TestInferenceParserAndValidation(unittest.TestCase):
    def test_parse_valid_json_verdicts(self):
        for v in ["SUPPORTED", "REFUTED", "UNVERIFIABLE"]:
            raw = f'{{"verdict": "{v}", "explanation": "Rationale for {v}."}}'
            parsed = parse_and_validate_llm_response(raw)
            self.assertEqual(parsed["verdict"], v)
            self.assertEqual(parsed["explanation"], f"Rationale for {v}.")
            self.assertEqual(parsed["confidence"], 1.0)

    def test_parse_json_markdown_blocks(self):
        raw = 'Here is the verdict:\n```json\n{\n  "verdict": "SUPPORTED",\n  "explanation": "Verified from SEC 10-K."\n}\n```'
        parsed = parse_and_validate_llm_response(raw)
        self.assertEqual(parsed["verdict"], "SUPPORTED")
        self.assertEqual(parsed["explanation"], "Verified from SEC 10-K.")

    def test_parse_confidence_extraction(self):
        raw = '{"verdict": "REFUTED", "explanation": "Contradicted.", "confidence": 0.85}'
        parsed = parse_and_validate_llm_response(raw)
        self.assertEqual(parsed["confidence"], 0.85)

    def test_disallowed_verdict_labels_raise_value_error(self):
        invalid_labels = ["TRUE", "FALSE", "NEI", "MAYBE", "PLAUSIBLE", "UNKNOWN", "MIXED"]
        for lbl in invalid_labels:
            raw = f'{{"verdict": "{lbl}", "explanation": "test"}}'
            with self.assertRaises(ValueError) as ctx:
                parse_and_validate_llm_response(raw)
            self.assertIn("Invalid verdict label", str(ctx.exception))

    def test_malformed_json_raises_value_error(self):
        invalid_payloads = [
            "",
            "   ",
            "This is plain text without JSON.",
            '{"verdict": "SUPPORTED", unclosed',
            "[]",
        ]
        for payload in invalid_payloads:
            with self.assertRaises(ValueError):
                parse_and_validate_llm_response(payload)


class TestInferenceExecutionAndErrorIsolation(unittest.TestCase):
    def test_mock_inference_success(self):
        def mock_requester(payload, attempt=1):
            return '{"verdict": "SUPPORTED", "explanation": "Mocked success."}'

        raw, parsed = request_ollama_inference(
            prompt="Claim test",
            max_retries=3,
            requester_fn=mock_requester,
        )
        self.assertEqual(parsed["verdict"], "SUPPORTED")
        self.assertEqual(parsed["explanation"], "Mocked success.")

    def test_mock_transient_failure_then_success(self):
        attempts_seen = []

        def mock_retry_requester(payload, attempt=1):
            attempts_seen.append(attempt)
            if attempt == 1:
                raise TimeoutError("Simulated socket timeout on attempt 1")
            return '{"verdict": "REFUTED", "explanation": "Succeeded on retry."}'

        raw, parsed = request_ollama_inference(
            prompt="Claim test",
            max_retries=3,
            retry_delay=0.0,
            requester_fn=mock_retry_requester,
        )
        self.assertEqual(parsed["verdict"], "REFUTED")
        self.assertEqual(attempts_seen, [1, 2])

    def test_mock_retry_exhaustion_raises_runtime_error(self):
        def mock_failing_requester(payload, attempt=1):
            raise ConnectionError("Simulated Ollama unreachable")

        with self.assertRaises(RuntimeError) as ctx:
            request_ollama_inference(
                prompt="Claim test",
                max_retries=3,
                retry_delay=0.0,
                requester_fn=mock_failing_requester,
            )
        self.assertIn("Inference failed after 3 attempts", str(ctx.exception))


class TestProgressCheckpointAndResumption(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.sample_path = self.project_root / "backend" / "data" / "finfact_research_sample.json"

    def test_atomic_progress_save_and_resume(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            out_file = tmppath / "condition_b4_results.json"
            audit_file = tmppath / "b4_inference_audit.json"
            prog_file = tmppath / "condition_b4_progress.json"

            # Pre-seed progress with 2 completed claims
            pre_records = [
                {
                    "claim_id": "finfact_000032",
                    "pipeline_status": STATUS_NO_RELEVANT_EVIDENCE,
                    "verdict": "UNVERIFIABLE",
                    "confidence": 0.0,
                    "raw_evidence_count": 1,
                    "accepted_evidence_count": 0,
                    "rejected_evidence_count": 1,
                    "accepted_evidence": [],
                    "rejected_evidence": [],
                },
                {
                    "claim_id": "finfact_000035",
                    "pipeline_status": STATUS_GROUNDED_SUCCESS,
                    "verdict": "SUPPORTED",
                    "confidence": 1.0,
                    "raw_evidence_count": 2,
                    "accepted_evidence_count": 1,
                    "rejected_evidence_count": 1,
                    "accepted_evidence": [{"retrieved_text": "text", "leakage_classification": "primary_source_citation"}],
                    "rejected_evidence": [],
                },
            ]
            save_progress_atomic(
                prog_file,
                pre_records,
                status_counts={STATUS_GROUNDED_SUCCESS: 1, STATUS_NO_RELEVANT_EVIDENCE: 1, STATUS_RETRIEVAL_ERROR: 0, STATUS_INFERENCE_ERROR: 0},
                leakage_stats={"total_raw_evidence_items": 3, "rejected_temporal": 0, "rejected_relevance": 0, "rejected_verdict_leakage": 0, "rejected_uncertain_leakage": 0, "accepted_primary_source": 1, "accepted_fact_checker_reporting": 0},
                temporal_setting="retrospective",
                dry_run=True,
            )

            self.assertTrue(prog_file.exists())

            # Now run pipeline with resume=True and dry_run=True
            summary = run_pipeline(
                sample_path=self.sample_path,
                output_path=out_file,
                audit_path=audit_file,
                dry_run=True,
                temporal_setting="retrospective",
                progress_path=prog_file,
                resume=True,
                retry_delay=0.0,
            )

            self.assertEqual(summary["total_claims"], 300)
            total = sum(summary["status_accounting"].values())
            self.assertEqual(total, 300)

            # Check that output contains all 300 claims
            with open(out_file, "r", encoding="utf-8") as f:
                saved_results = json.load(f)
            self.assertEqual(len(saved_results), 300)

            # Claim 35 should retain its pre-seeded verdict
            c35 = next(r for r in saved_results if r["claim_id"] == "finfact_000035")
            self.assertEqual(c35["verdict"], "SUPPORTED")

    def test_inference_error_isolated_and_not_converted_to_unverifiable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            out_file = tmppath / "condition_b4_results.json"
            audit_file = tmppath / "b4_inference_audit.json"

            def always_fail_requester(payload, attempt=1):
                raise RuntimeError("Ollama server crash simulation")

            # Run with full inference (dry_run=False) on failing requester
            summary = run_pipeline(
                sample_path=self.sample_path,
                output_path=out_file,
                audit_path=audit_file,
                dry_run=False,
                temporal_setting="retrospective",
                retry_delay=0.0,
                requester_fn=always_fail_requester,
            )

            # All claims that had evidence must record STATUS_INFERENCE_ERROR, NOT STATUS_NO_RELEVANT_EVIDENCE
            self.assertEqual(summary["total_claims"], 300)
            status_counts = summary["status_accounting"]
            total = sum(status_counts.values())
            self.assertEqual(total, 300)
            self.assertEqual(status_counts[STATUS_INFERENCE_ERROR], 232)
            self.assertEqual(status_counts[STATUS_NO_RELEVANT_EVIDENCE], 68)
            self.assertEqual(status_counts[STATUS_GROUNDED_SUCCESS], 0)

            # Inspect saved file to ensure verdict is INFERENCE_ERROR, NOT UNVERIFIABLE
            with open(out_file, "r", encoding="utf-8") as f:
                saved_results = json.load(f)
            grounded_claims = [r for r in saved_results if r["pipeline_status"] == STATUS_INFERENCE_ERROR]
            self.assertEqual(len(grounded_claims), 232)
            for gc in grounded_claims:
                self.assertEqual(gc["verdict"], "INFERENCE_ERROR")
                self.assertIn("Ollama server crash simulation", gc["error"])


if __name__ == "__main__":
    unittest.main()
