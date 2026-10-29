"""
test_platform_validation.py

End-to-end local platform validation suite.
Exercises Flask API endpoints for all three verification methods:
1. Condition A: Internal Knowledge LLM (Ollama)
2. Model B: MPNet Supervised Classifier
3. Condition B: External Evidence Retrieval

Tests:
- Valid claims
- Empty input
- Offline service handling (Ollama 503)
- API errors & malformed input
- Strict non-substitution verification
"""

import json
from pathlib import Path
import unittest

from app import app
from research.canonical_mapping import CLASSES, verify_manifest
from research.classifier_service import classify_financial_claims, get_classifier_components


class TestPlatformEndToEndValidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def test_01_manifest_integrity(self):
        """Confirm all 7 protected files remain intact."""
        ok, report = verify_manifest()
        self.assertTrue(ok, f"SHA-256 Manifest check failed: {report}")

    def test_02_mpnet_classifier_direct(self):
        """Verify saved MPNet classifier loads and predicts correctly."""
        tokenizer, model, clf = get_classifier_components()
        self.assertIsNotNone(tokenizer)
        self.assertIsNotNone(model)
        self.assertIsNotNone(clf)
        claims = [{"claim_id": "CLM-01", "claim_text": "Apple reported total net sales of $383,285 million."}]
        results = classify_financial_claims(claims)
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertIn(res["verdict"], CLASSES)
        self.assertGreaterEqual(res["confidence"], 0.0)
        self.assertLessEqual(res["confidence"], 1.0)
        self.assertIn("probabilities", res)
        prob_sum = sum(res["probabilities"].values())
        self.assertAlmostEqual(prob_sum, 1.0, places=3)

    def test_03_condition_a_offline_ollama_handling(self):
        """Condition A must return HTTP 503 and clear offline details when Ollama is down."""
        payload = {
            "claims": [
                {"claim_id": "CLM-01", "claim_text": "Pfizer reported total revenues of $100.3 billion in 2022."}
            ]
        }
        resp = self.client.post("/api/verify/internal", json=payload)
        self.assertEqual(resp.status_code, 503)
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("offline", data["error"].lower())
        self.assertIn("ollama serve", data["details"].lower())
        self.assertEqual(data["claims"][0]["verdict"], "ERROR")
        self.assertEqual(data["claims"][0]["condition"], "internal")
        # Ensure zero silent substitution
        self.assertNotIn("probabilities", data["claims"][0])
        self.assertEqual(len(data["claims"][0]["evidence"]), 0)

    def test_04_condition_a_empty_and_invalid_inputs(self):
        """Test Condition A with empty and invalid inputs."""
        resp = self.client.post("/api/verify/internal", json={"claims": []})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["claims"], [])

        resp = self.client.post("/api/verify/internal", json={"claims": "not-a-list"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_05_model_b_classifier_valid_claims(self):
        """Model B must return 200, valid probabilities, empty evidence, and distinct schema."""
        payload = {
            "claims": [
                {"claim_id": "CLM-01", "claim_text": "Financial headlines falsely claimed that Apple reported total net sales of $950 billion for fiscal year 2023."},
                {"claim_id": "CLM-02", "claim_text": "Apple reported total net sales of $383,285 million for fiscal year 2023."}
            ]
        }
        resp = self.client.post("/api/verify/classifier", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["condition"], "classifier")
        self.assertEqual(len(data["claims"]), 2)

        for c in data["claims"]:
            self.assertEqual(c["condition"], "classifier")
            self.assertEqual(c["evaluator_type"], "SUPERVISED_CLASSIFIER_MPNET")
            self.assertIn(c["verdict"], CLASSES)
            self.assertIn("probabilities", c)
            self.assertAlmostEqual(sum(c["probabilities"].values()), 1.0, places=3)
            self.assertEqual(c["evidence"], [])  # Model B performs no evidence retrieval

    def test_06_model_b_empty_and_invalid_inputs(self):
        """Test Model B with empty and invalid inputs."""
        resp = self.client.post("/api/verify/classifier", json={"claims": []})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["claims"], [])

        resp = self.client.post("/api/verify/classifier", json={"claims": 12345})
        self.assertEqual(resp.status_code, 400)

    def test_07_condition_b_evidence_grounded(self):
        """Condition B must return 200, retrieve evidence snippets, and cite sources."""
        payload = {
            "claims": [
                {"claim_id": "CLM-01", "claim_text": "Apple reported total net sales of $383,285 million ($383.29 billion) for fiscal year 2023."}
            ],
            "use_demo_evidence": True
        }
        resp = self.client.post("/api/verify/evidence", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["claims"]), 1)
        claim = data["claims"][0]
        self.assertEqual(claim["condition"], "evidence")
        self.assertIn(claim["verdict"], CLASSES)
        self.assertGreater(len(claim["evidence"]), 0)
        self.assertIn("evidence_text", claim["evidence"][0])

    def test_08_strict_non_substitution_across_methods(self):
        """Verify each method preserves its own distinct identity and output structure."""
        claim_payload = {"claims": [{"claim_id": "CLM-SAME", "claim_text": "Apple reported total net sales of $383,285 million for fiscal year 2023."}]}

        resp_a = self.client.post("/api/verify/internal", json=claim_payload)
        resp_b = self.client.post("/api/verify/classifier", json=claim_payload)
        resp_c = self.client.post("/api/verify/evidence", json={"claims": claim_payload["claims"], "use_demo_evidence": True})

        # Condition A: 503 error
        self.assertEqual(resp_a.status_code, 503)
        res_a_claim = resp_a.get_json()["claims"][0]
        self.assertEqual(res_a_claim["condition"], "internal")
        self.assertEqual(res_a_claim["verdict"], "ERROR")

        # Model B: 200 with classifier condition, probabilities, no evidence
        self.assertEqual(resp_b.status_code, 200)
        res_b_claim = resp_b.get_json()["claims"][0]
        self.assertEqual(res_b_claim["condition"], "classifier")
        self.assertIn("probabilities", res_b_claim)
        self.assertEqual(res_b_claim["evidence"], [])

        # Condition B: 200 with evidence condition, non-empty evidence
        self.assertEqual(resp_c.status_code, 200)
        res_c_claim = resp_c.get_json()["claims"][0]
        self.assertEqual(res_c_claim["condition"], "evidence")
        self.assertGreater(len(res_c_claim["evidence"]), 0)


if __name__ == "__main__":
    unittest.main()
