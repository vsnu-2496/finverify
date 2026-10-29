"""
test_classifier_endpoint.py

Unit tests for POST /api/verify/classifier, classifier service,
and improved offline error handling for Condition A.
"""

from pathlib import Path
import unittest
from unittest.mock import patch
import requests

from app import app
from research.canonical_mapping import CLASSES
from research.classifier_service import (
    classify_financial_claims,
    extract_claim_embedding,
    get_classifier_components,
)


class TestClassifierServiceAndEndpoint(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    def test_classifier_endpoint_valid_claim(self):
        response = self.client.post(
            "/api/verify/classifier",
            json={
                "claims": [
                    {
                        "claim_id": "CLM-TEST-01",
                        "claim_text": "Apple Inc. reported fourth quarter revenue of $89.5 billion.",
                    }
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["condition"], "classifier")
        self.assertEqual(len(data["claims"]), 1)

        c = data["claims"][0]
        self.assertEqual(c["claim_id"], "CLM-TEST-01")
        self.assertIn(c["verdict"], CLASSES)
        self.assertTrue(0.0 <= c["confidence"] <= 1.0)
        self.assertIsInstance(c["probabilities"], dict)
        for cls in CLASSES:
            self.assertIn(cls, c["probabilities"])
        self.assertAlmostEqual(sum(c["probabilities"].values()), 1.0, places=2)
        # Supervised classifier does not fabricate or retrieve documents
        self.assertEqual(c["evidence"], [])
        self.assertEqual(c["condition"], "classifier")

    def test_classifier_endpoint_empty_claim_text(self):
        response = self.client.post(
            "/api/verify/classifier",
            json={
                "claims": [
                    {"claim_id": "CLM-EMPTY", "claim_text": ""}
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        c = data["claims"][0]
        self.assertEqual(c["status"], "error")
        self.assertEqual(c["verdict"], "ERROR")
        self.assertIn("empty", c["explanation"].lower())

    def test_classifier_endpoint_invalid_payload_not_list(self):
        response = self.client.post(
            "/api/verify/classifier",
            json={"claims": "This should be a list, not a string"},
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("must be a list", data["error"])

    def test_classifier_missing_artifact_raises(self):
        with self.assertRaises(FileNotFoundError):
            classify_financial_claims(
                claims=[{"claim_id": "1", "claim_text": "test"}],
                artifact_path=Path("non_existent_classifier_artifact.joblib"),
            )

    @patch("requests.post")
    def test_internal_verification_offline_ollama_returns_503(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused: 11434")

        response = self.client.post(
            "/api/verify/internal",
            json={
                "claims": [
                    {"claim_id": "CLM-OLLAMA", "claim_text": "Federal Reserve increased rates."}
                ]
            },
        )
        self.assertEqual(response.status_code, 503)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("offline", data["error"].lower())
        self.assertIn("ollama serve", data["details"])
        self.assertEqual(len(data["claims"]), 1)
        self.assertEqual(data["claims"][0]["verdict"], "ERROR")


if __name__ == "__main__":
    unittest.main()
