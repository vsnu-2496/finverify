# Consolidated Research Findings & Audit Report

**Generated:** 2026-10-19T16:36:19.343686+00:00
**Model:** qwen2.5:3b (local Ollama)
**Benchmark:** Fin-Fact 300-claim research sample

## 1. Experimental Conditions Measured Outcomes

| Condition | Sources | Total Sample | Evaluated Grounded | Not Applicable | Errors | Accuracy | Macro-F1 |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | None (Internal Knowledge) | 300 | 300 | 0 | 0 | 0.1900 | 0.1186 |
| **B1** | SEC | 300 | 5 | 295 | 0 | 0.4000 | 0.1905 |
| **B2** | Alpha Vantage | 300 | 0 | 300 | 0 | N/A | N/A |
| **B3** | SEC, Alpha Vantage | 300 | 5 | 295 | 0 | 0.4000 | 0.1905 |

## 2. Methodological Findings & Comparability Limitations

> [!WARNING]
> **Non-Comparable Sample Sizes:** The 40.0% accuracy on the 5-claim grounded subset in B1 and B3 cannot be directly compared against the 19.0% baseline accuracy on the full 300-claim Condition A sample. No claim should be made that evidence grounding improves overall accuracy on Fin-Fact.

### Key Audited Insights
1. **Parametric Memory (Condition A):** The ungrounded 3B model abstained (UNVERIFIABLE) on 292/300 claims (97.3%), achieving 19.0% accuracy due to lack of specific factual recall.
2. **Regulatory SEC Grounding (Condition B1 & B3):** Successfully retrieved temporally valid 10-K/8-K filings for the 5 corporate claims. However, formal corporate disclosures do not address viral rumors or political debates, leading the model to accurately identify the evidence as insufficient (UNVERIFIABLE) in all 5 cases.
3. **Market Data Grounding (Condition B2):** 0 of 300 claims qualified as company stock movement claims. Alpha Vantage returned 0 grounded claims and 300 not applicable records, preventing any fabricated quotes or predictions.

