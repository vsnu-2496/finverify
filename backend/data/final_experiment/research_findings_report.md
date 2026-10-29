# Experiment Configuration and Findings Report

**Research Title:** Evidence-Grounded vs. Internal-Knowledge Verification: A Comparative Study of LLM Misinformation Detection in Financial News  
**Date:** October 15, 2026  
**Benchmarking Environment:** Local Inference (`Ollama`, model `qwen2.5:3b`, parameters 3.1B, Q4_K_M quantization)  
**Dataset:** Fin-Fact (Financial Fact-Checking Dataset, 3,369 verified real-world financial claims)  
**Sample Specification:** Stratified random sample of $n = 300$ claims (random seed 42), preserved across all conditions.  
**Class Distribution:** 133 REFUTED (`false`), 113 SUPPORTED (`true`), 54 UNVERIFIABLE (`NEI`).

---

## 1. Verified Experimental Outcomes by Condition

| Condition | Description | Required Sources | Evaluated Claims | Valid Completed Records | Condition Status |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **Condition A** | Internal Knowledge Verification | None (Parametric memory only) | **300 / 300** | **300** | **COMPLETED** |
| **Condition B1** | SEC EDGAR Evidence | SEC EDGAR Submissions / CompanyFacts | 0 / 300 | 0 | **BLOCKED** (Missing SEC Contact User-Agent; 0 claims yielded evidence) |
| **Condition B2** | Market Data Evidence | Alpha Vantage Global Quote / Overview | 0 / 300 | 0 | **BLOCKED** (Inapplicable claim semantics; historical daily quotes cannot test causal claims) |
| **Condition B3** | Combined SEC + Market | SEC EDGAR + Alpha Vantage | 0 / 300 | 0 | **BLOCKED** (Cumulative dependencies from B1 and B2) |

---

## 2. Condition A Measured Findings

Condition A relies strictly on the LLM's parametric knowledge with no external search, browsing, SEC filings, or market data.

### Overall Performance
- **Evaluated Claims:** 300
- **Accuracy:** 0.1900 (57 / 300 correct)
- **Macro Precision:** 0.3116
- **Macro Recall:** 0.3409
- **Macro F1:** 0.1186

### Class-Level Breakdown

| Class | Support ($n$) | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: |
| **SUPPORTED** | 113 | 0.0000 | 0.0000 | 0.0000 |
| **REFUTED** | 133 | 0.7500 | 0.0226 | 0.0438 |
| **UNVERIFIABLE** | 54 | 0.1849 | 1.0000 | 0.3121 |

### Confusion Matrix
Rows represent true gold labels; columns represent model predictions:

| Gold \ Predicted | SUPPORTED | REFUTED | UNVERIFIABLE | Total |
| :--- | :---: | :---: | :---: | :---: |
| **SUPPORTED** | 0 | 1 | 112 | 113 |
| **REFUTED** | 4 | 3 | 126 | 133 |
| **UNVERIFIABLE** | 0 | 0 | 54 | 54 |
| **Total Predicted** | 4 | 4 | 292 | 300 |

### Key Observations
1. **Conservative / Abstention Bias:** When prompted to only answer if confident and default to `UNVERIFIABLE`, `qwen2.5:3b` abstained on 292 out of 300 claims (97.3%).
2. **Parametric Financial Blindness:** The model demonstrated virtually no internal memory of specific historical corporate events, filings, or numbers, correctly identifying only 3 refuted claims and 0 supported claims.
3. **Absence of Evidence-Grounded Comparison:** Because external evidence retrieval in B1, B2, and B3 yielded 0 validated records on this benchmark, **no scientific claim can be made that evidence grounding improves accuracy on this sample**. The Condition A results serve as the sole verified empirical baseline.

---

## 3. Provenance & Artifact Hashes

- **Condition A Results Path:** `backend/data/condition_a_ollama_qwen25_3b_results.json`
  - SHA256: `6a6dd6daa0fe06320fcb80073da0a35da9276143b5bcb6d65ff3d28fc0ecfe8c`
- **Research Sample Path:** `backend/data/finfact_research_sample.json`
  - SHA256: `1ccb1356ddd7ed86fc990b174bd883ac31cd3116e1f4cd9c60cb52f9276be6ad`
- **Evaluation Labels Path:** `backend/data/finfact_research_evaluation.json`
  - SHA256: `0a7dca7e7f178c5187bf42858818eb3183d36dcdb9d83545a79b18721e3bf62f`
- **Generated CSVs & Vectors:** `backend/data/final_experiment/`
  - `condition_a_metrics.csv`
  - `condition_a_metrics.json`
  - `condition_a_per_class.csv`
  - `condition_a_confusion_matrix.csv`
  - `condition_a_overview.svg`
  - `condition_a_per_class_metrics.svg`
  - `condition_a_confusion_matrix.svg`
