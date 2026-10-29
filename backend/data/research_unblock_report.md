# Research Pipeline Unblock Report

**Updated:** 2026-10-12

## Outcome

Ollama runtime was restored. The B2/B3 evidence-grounded experiments remain
blocked by source eligibility and access requirements; neither was run in this
execution. No prediction was generated from missing or synthetic evidence.

Condition A, B1, benchmark records, publication dates, and gold labels were not
modified. Existing invalid B2 results and their backup were preserved.

## Runtime

- Existing Ollama executable: `C:\Users\vishn\Ollama\ollama.exe`.
- Initially, port 11434 had no listener. Started the existing executable with
  `ollama serve`; did not start a duplicate.
- Verified the local API responds at `http://localhost:11434/api/tags` and
  reports `qwen2.5:3b` installed.
- The Alpha Vantage key is loaded from configuration. Its value was not
  displayed.

## SEC access and five-claim preflight

`SEC_USER_AGENT` is not present in the environment or backend `.env`. The
retriever correctly refuses to send requests without an identifying User-Agent
containing a real contact email. Accordingly, no SEC network requests were
made, and no SEC evidence was established in this execution.

The five applicable claims were run through the retrieval preflight; each was
stopped at the contact-identity validation gate:

| Claim ID | Claim date | Resolved entity | Preflight status |
|---|---|---|---|
| `finfact_000462` | 2021-02-10 | Costco Wholesale Corporation | `error`: required SEC_USER_AGENT is not configured |
| `finfact_000596` | 2008-10-02 | Federal National Mortgage Association | `error`: required SEC_USER_AGENT is not configured |
| `finfact_000786` | 2016-10-23 | Ford Motor Co. | `error`: required SEC_USER_AGENT is not configured |
| `finfact_001599` | 2021-06-22 | American Airlines Group Inc. | `error`: required SEC_USER_AGENT is not configured |
| `finfact_002061` | 2009-03-18 | American International Group, Inc. | `error`: required SEC_USER_AGENT is not configured |

Earlier retrieval history recorded HTTP 403 for the American Airlines archive
request. It was not retried or bypassed. The other claims have not been
retested against SEC in this execution because a legitimate contact identity
is unavailable. No claim is classified as `UNVERIFIABLE` on the basis of these
retrieval failures.

Machine-readable preflight results:
`condition_b3_sec_preflight_20261012.json`.

## B2 source suitability

The fixed 300-claim sample has no claims eligible for the current Alpha
Vantage stock-evidence path. Earlier inspection of the original Fin-Fact
corpus found market-language claims, but the identified Target claims ask
whether a policy caused a stock-price movement. Price series alone cannot
establish that causal claim. Historical news and index endpoints were
previously found to be premium-only for the configured Alpha Vantage access.
No supplementary benchmark was created: there is not a defensible set of
claims for which the currently accessible Alpha Vantage evidence can test the
claim semantics. The original sample and its labels were left unchanged.

## Saved experiment status

| Condition | Saved rows | Evidence-grounded valid rows | Disposition |
|---|---:|---:|---|
| A | 300 successful | 300 (internal-knowledge condition) | Completed baseline; valid for its design. |
| B1 | 300 marked successful | 0 | Legacy records contain no evidence; not accepted as an evidence-grounded result. |
| B2 | 269 marked successful, 31 errors | 0 | Legacy records all lack evidence; predictions are invalid for B2 and were not reused. |
| B3 | No active Ollama result file | 0 | Not run: SEC identity configuration missing; Alpha Vantage is inapplicable to this sample. |

The legacy `condition_b3_combined_results.json` is not an active completed
Ollama B3 result and contains no evidence. It was not treated as valid output.

## Metrics

Only condition A has valid completed predictions for evaluation:

- Evaluated claims: **300**
- Accuracy: **0.1900**
- Macro precision: **0.3116**
- Macro recall: **0.3409**
- Macro-F1: **0.1186**

| Gold class | Precision | Recall | F1 |
|---|---:|---:|---:|
| REFUTED | 0.7500 | 0.0226 | 0.0438 |
| SUPPORTED | 0.0000 | 0.0000 | 0.0000 |
| UNVERIFIABLE | 0.1849 | 1.0000 | 0.3121 |

Confusion matrix (rows = gold; columns = predicted):

|  | REFUTED | SUPPORTED | UNVERIFIABLE |
|---|---:|---:|---:|
| REFUTED | 3 | 4 | 126 |
| SUPPORTED | 1 | 0 | 112 |
| UNVERIFIABLE | 0 | 0 | 54 |

No B1, B2, or B3 metrics are reported because there are zero
evidence-validated predictions for those conditions. No cross-condition
improvement claim is supported.

## Tests and code changes

- Backend test suite: **18 passed**.
- Python syntax compilation for `app.py`, the experiment runner, and the
  focused test module: passed.
- No source-code changes were required during this execution. Existing resume
  validation and retrieval tests were exercised.

## Output preservation

- Existing A results: `condition_a_ollama_qwen25_3b_results.json`
- Existing B1 results: `condition_b1_ollama_qwen25_3b_results.json`
- Invalid B2 results/progress retained:
  `condition_b2_ollama_qwen25_3b_results.json` and
  `condition_b2_ollama_qwen25_3b_progress.json`
- Existing B2 backup retained:
  `backups/condition_b2_pre_resume_20261011T133440Z/`
- No active B3 Ollama results or progress were created.

## Remaining action

Supply `SEC_USER_AGENT` through `backend/.env` or the process environment in
the form `Organization Name contact@example.org`, using a real organization
and contact email authorized for this research. Then rerun the five-claim SEC
preflight. Only claims with actual, relevant evidence filed no later than the
claim date can proceed to B3. Alpha Vantage B2 remains blocked until a
defensible eligible benchmark and suitable historical/source evidence access
are available.

## Follow-up audit — 2026-10-12 17:26 (+05:30)

- Read this report and
  `condition_b3_sec_preflight_20261012.json`.
- Rechecked `SEC_USER_AGENT` from the loaded backend environment without
  printing its value. It remains absent; no contact-shaped identity is
  configured. **No SEC request was made.**
- The existing five-claim machine-readable preflight remains the last
  retrieval record. Its five records show the required identity configuration
  error and zero evidence. It must not be interpreted as a live SEC response.
- Re-ran the backend test suite: **18 passed**.
- Confirmed A and B1 result/progress files are unchanged from their recorded
  SHA-256 hashes:
  - A results: `6a6dd6daa0fe06320fcb80073da0a35da9276143b5bcb6d65ff3d28fc0ecfe8c`
  - A progress: `aba3b1f83cd0dcc393895558ff3f9f4758c941eda27adb5f5dd6357c4772f363`
  - B1 results: `bee756c60cec74782afcc7c6107d68f07de773a85edd46a2757641d7bb58e5f3`
  - B1 progress: `a6202873e55da7540d0a61fdc3a74d7b8149340ded258c0d181161d22d4afd96`
- Confirmed both saved B2 files still match the preserved audit backup. No
  experiment results or metrics were changed or added.
- B3 remains **not run**; B2 remains **not run** on a supplementary set.

Required next action for SEC is unchanged: configure an authorized,
real-contact `SEC_USER_AGENT`, then rerun the five-claim retrieval preflight.

## Measured-results follow-up — 2026-10-12

Generated a reproducible Condition A results package from the saved Ollama
predictions. The generator validates that the ordered claim IDs in the sample,
gold-label evaluation file, and A results align exactly, and requires 300
successful predictions with valid verdicts before calculating metrics. It
writes only to `data/measured_results_20261012/`; the original result files
remain read-only.

Condition A (n = 300):

| Metric | Value |
|---|---:|
| Accuracy | 0.1900 |
| Macro precision | 0.3116 |
| Macro recall | 0.3409 |
| Macro-F1 | 0.1186 |

| Gold class | Precision | Recall | F1 |
|---|---:|---:|---:|
| SUPPORTED | 0.0000 | 0.0000 | 0.0000 |
| REFUTED | 0.7500 | 0.0226 | 0.0438 |
| UNVERIFIABLE | 0.1849 | 1.0000 | 0.3121 |

The package contains a machine-readable metric record, summary and per-class
CSVs, and three vector graphs:

- `measured_results_20261012/condition_a_overview.svg`
- `measured_results_20261012/condition_a_per_class_metrics.svg`
- `measured_results_20261012/condition_a_confusion_matrix.svg`
- `measured_results_20261012/condition_a_metrics.json`
- `measured_results_20261012/condition_a_metrics.csv`
- `measured_results_20261012/condition_a_per_class.csv`
- `measured_results_20261012/condition_a_confusion_matrix.csv`

Reproduce with `python -m research.generate_measured_results` from `backend`.
The generator is `research/generate_measured_results.py`. Output metadata
records SHA-256 hashes for the Condition A results, fixed sample, and
evaluation labels.

This execution did not make SEC requests: `SEC_USER_AGENT` remains absent.
Therefore B1/B3 still have zero evidence-validated predictions, and neither
was run. B2 remains unrun: the original sample contains no eligible claims,
and no defensible supplementary market-claim benchmark was established. No
metrics or graphs are presented for B1, B2, or B3.
