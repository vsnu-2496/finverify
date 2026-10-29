"""Smoke test verifying Priority 2 test cases:
1. A claim that has relevant public financial evidence.
2. A claim outside the supported evidence sources.
3. A claim with insufficient evidence.
4. A simulated or controlled retrieval failure.
"""

import json
import os
import sys
from pathlib import Path
from datetime import date

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import app

print("=" * 60)
print("PRIORITY 2: END-TO-END SMOKE TEST")
print("=" * 60)

# TEST CASE 1: Claim with relevant public financial evidence
print("\n--- Test Case 1: Claim with relevant public financial evidence ---")
claim_1 = "Ford is moving all of their small-car production to Mexico."
evidence_1 = [{
    "evidence_id": "ev_sec_1",
    "source": "SEC EDGAR",
    "url": "https://www.sec.gov/Archives/edgar/data/37996/000003799616000153/sales8-kdated10x3x2016.htm",
    "evidence_date": "2016-10-03",
    "evidence_text": "Ford Motor Company confirmed that production of its Focus and C-MAX small car lines will be moved to a newly constructed assembly facility in San Luis Potosi, Mexico."
}]
res_1 = app._verify_claim_with_evidence(claim_1, evidence_1)
print(f"Claim: {claim_1}")
print(f"Supplied Evidence Count: {len(evidence_1)}")
print(f"Verdict: {res_1['verdict']}")
print(f"Confidence: {res_1['confidence']}")
print(f"Explanation: {res_1['explanation']}")
assert res_1["verdict"] in ["SUPPORTED", "REFUTED"], f"Expected supported/refuted, got {res_1['verdict']}"

# TEST CASE 2: Claim outside supported evidence sources (Non-corporate political claim)
print("\n--- Test Case 2: Claim outside supported evidence sources ---")
claim_2 = "Did Sarah Palin Say People with Lyme Disease Should Stop Eating Limes?"
cl_2 = app._classify_financial_claim(claim_2)
sec_ev_2, sec_err_2 = app._retrieve_sec_evidence(claim_2, cl_2["claim_type"], cl_2["entity"], date(2017, 5, 8))
av_ev_2, av_err_2 = app._retrieve_alpha_vantage_evidence(claim_2, cl_2["claim_type"], cl_2["entity"], date(2017, 5, 8))
print(f"Claim: {claim_2}")
print(f"Identified Entity: {cl_2['entity']}")
print(f"SEC Status: {sec_err_2[0]['status']} - {sec_err_2[0]['error']}")
print(f"Alpha Vantage Status: {av_err_2[0]['status']} - {av_err_2[0]['error']}")
assert sec_err_2[0]["status"] == "not_applicable"
assert av_err_2[0]["status"] == "not_applicable"

# TEST CASE 3: Claim with insufficient / inconclusive evidence
print("\n--- Test Case 3: Claim with insufficient evidence ---")
claim_3 = "Costco is shutting down 50% of all its retail warehouses nationwide."
evidence_3 = [{
    "evidence_id": "ev_sec_3",
    "source": "SEC EDGAR",
    "url": "https://www.sec.gov/Archives/edgar/data/909832/sample10q.htm",
    "evidence_date": "2021-01-15",
    "evidence_text": "Costco Wholesale Corporation opened 8 new warehouse locations during the first quarter and plans to open 12 additional locations throughout the fiscal year."
}]
res_3 = app._verify_claim_with_evidence(claim_3, evidence_3)
print(f"Claim: {claim_3}")
print(f"Supplied Evidence: {evidence_3[0]['evidence_text']}")
print(f"Verdict: {res_3['verdict']}")
print(f"Confidence: {res_3['confidence']}")
print(f"Explanation: {res_3['explanation']}")
# The evidence shows openings, which either refutes or leaves the exact 50% claim unverifiable/refuted
assert res_3["verdict"] in ["REFUTED", "UNVERIFIABLE"]

# TEST CASE 4: Controlled retrieval technical failure
print("\n--- Test Case 4: Controlled retrieval failure ---")
# Simulate an invalid SEC response / network failure
claim_4 = "Apple revenue grew 15% year over year."
# Test with forced invalid headers to trigger controlled technical failure
try:
    old_ua = os.environ.get("SEC_USER_AGENT", "")
    os.environ["SEC_USER_AGENT"] = "INVALID_NO_EMAIL"
    failed_ev, failed_err = app._retrieve_sec_evidence(claim_4, "financial/revenue", app.SEC_COMPANIES["apple"], date(2021, 10, 1))
    print("Controlled Failure Caught:")
    print(f"  Status: {failed_err[0]['status']}")
    print(f"  Error message: {failed_err[0]['error']}")
    assert failed_err[0]["status"] == "error"
    assert "SEC_USER_AGENT" in failed_err[0]["error"]
finally:
    if old_ua:
        os.environ["SEC_USER_AGENT"] = old_ua
    else:
        os.environ.pop("SEC_USER_AGENT", None)

print("\n" + "=" * 60)
print("ALL 4 SMOKE TEST CASES PASSED SUCCESSFULLY!")
print("=" * 60)
