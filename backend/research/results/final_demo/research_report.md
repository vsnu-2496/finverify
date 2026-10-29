# Evidence-Grounded vs. Internal-Knowledge Verification

## 1. Title
Evidence-Grounded vs. Internal-Knowledge Verification: A Comparative Study of LLM Misinformation Detection in Financial News

## 2. Research objective
Evaluate the software pipeline for comparing internal-knowledge and evidence-grounded verification on a fixed Fin-Fact pilot. These local results validate execution and visualization only.

## 3. Dataset
Fin-Fact contains 3,369 records. The fixed research pilot contains 75 claims: 25 SUPPORTED, 25 REFUTED, and 25 UNVERIFIABLE, selected deterministically with seed 42. Claim dates are preserved in ISO format.

## 4. Experimental design
The same ordered 75 claims are used in every condition. Gold labels are retained only for evaluation. Safe verifier inputs contain claim ID, claim text, and claim date. User-uploaded news remains separate demo data.

## 5. Condition A
A_INTERNAL_KNOWLEDGE uses the deterministic local fallback verifier with no external evidence. It is labeled DEMO_FALLBACK, not REAL_LLM.

## 6. Condition B
B1 uses synthetic SEC-style evidence, B2 uses synthetic market-data-style evidence, and B3 uses combined synthetic evidence. None is a real SEC, Alpha Vantage, or web response.

## 7. Evaluation metrics
Accuracy, macro precision, macro recall, macro F1, class-wise F1, and confusion matrices are calculated over the 75 demonstration predictions. They are software-pipeline outputs, not research conclusions.

## 8. Results
- **A_INTERNAL_KNOWLEDGE**: accuracy 0.3467, macro F1 0.3490
- **B1_SEC_STYLE**: accuracy 0.4000, macro F1 0.3978
- **B2_MARKET_STYLE**: accuracy 0.3067, macro F1 0.3017
- **B3_COMBINED**: accuracy 0.3067, macro F1 0.2990

## 9. Comparison
The full comparison is stored in `comparison_demo_75.json` and `comparison_demo_75.csv`. Differences here do not establish that evidence improves LLM performance because no real LLM predictions were produced.

## 10. Limitations
- These demonstration results are produced by a deterministic fallback verifier because the Gemini API free-tier quota was exhausted. They are intended to validate the experimental software pipeline and visualization, not to represent measured LLM performance.
- Real Gemini execution requires available API quota.
- Synthetic evidence is not external financial evidence.
- Demo fallback output must not be presented as measured LLM performance.
- User-uploaded articles do not contribute to Fin-Fact research accuracy.

## 11. Reproducibility
Run `python -m research.run_condition_a_demo` and `python -m research.run_condition_b_demo` from `backend`. The dataset, label mapping, seed, pilot IDs, and deterministic rules remain fixed.

## 12. Future work
Repeat the same pilot in REAL_LLM mode after quota is available, then compare conditions using the unchanged claim IDs, dates, prompts, and leakage controls.
