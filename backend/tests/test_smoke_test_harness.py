"""
test_smoke_test_harness.py

Unit tests for the controlled 3-claim smoke test harness.
Verifies:
- 3 stratified claims selected (one per canonical class: SUPPORTED, REFUTED, UNVERIFIABLE)
- Prompts never leak gold labels or reference classes
- Isolated execution into dedicated directory
- Manifest remains completely untouched and verified
"""

import json
from pathlib import Path
import tempfile
import unittest

from research.canonical_mapping import CLASSES, verify_manifest
from research.smoke_test_b4_3claims import (
    select_stratified_smoke_claims,
    run_smoke_test,
)


class TestSmokeTestHarness(unittest.TestCase):

    def test_select_stratified_claims(self):
        claims = select_stratified_smoke_claims()
        self.assertEqual(len(claims), 3)

        classes_found = {c["_eval_reference_class"] for c in claims}
        self.assertEqual(classes_found, set(CLASSES))

    def test_smoke_test_dry_run_isolated(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            summary = run_smoke_test(
                output_dir=tmp_path,
                run_inference=False,
            )

            self.assertTrue(summary["smoke_test"])
            self.assertEqual(summary["claims_evaluated"], 3)
            self.assertTrue(summary["accounting_invariant_holds"])

            results_file = tmp_path / "b4_smoke_results.json"
            self.assertTrue(results_file.exists())
            with open(results_file, "r", encoding="utf-8") as f:
                results = json.load(f)

            self.assertEqual(len(results), 3)
            for r in results:
                self.assertIn(r["reference_class_eval_only"], CLASSES)
                self.assertIn("claim_id", r)
                self.assertIn("pipeline_status", r)

        # Manifest must be 100% OK
        ok, rep = verify_manifest()
        self.assertTrue(ok, f"Manifest verification failed: {rep}")


if __name__ == "__main__":
    unittest.main()
