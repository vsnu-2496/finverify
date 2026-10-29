# B2/B3 Evidence Preflight Report — 2026-10-12

## Outcome

Neither B2 nor B3 was run. No new experiment results or B2/B3 metrics were
created. The B2 claims currently in the results file have no evidence and are
not valid evidence-grounded predictions.

The 300-claim benchmark, labels, publication dates, A results, and B1 results
were not modified.

## Tests and runtime

- Backend tests: 18 passed.
- Python syntax compilation for the research runner and tests: passed.
- Ollama was reachable and `qwen2.5:3b` was installed at the preceding
preflight.
- `ALPHA_VANTAGE_API_KEY` loaded without displaying its value.
- `SEC_USER_AGENT` is not configured. No SEC request was made in this preflight.

## Condition status and source coverage

| Condition | Saved status | Evidence-validated claims | Coverage / disposition |
|---|---:|---:|---|
| A | 300 successful | 300 | Valid internal-knowledge baseline; no external evidence expected. |
| B1 | 300 marked successful | 0 | Existing rows contain no evidence and record `not_applicable` for SEC; not counted as evidence-grounded results. |
| B2 | 269 marked successful, 31 errors | 0 | Every saved row has empty evidence. These legacy predictions are invalid for B2 and were not reused. Current 300-claim preflight found 0 Alpha Vantage-applicable claims. |
| B3 | Active Ollama result file absent | 0 | Five SEC-applicable claims are blocked by missing `SEC_USER_AGENT`; Alpha Vantage is not applicable to all 300 claims. The legacy `condition_b3_combined_results.json` contains errors and no evidence; it is not a completed B3 run. |

The five SEC-applicable benchmark claims are:

| Claim ID | Claim date | Current SEC preflight |
|---|---|---|
| `finfact_000462` | 2021-02-10 | Blocked before network access: no contact-bearing SEC User-Agent. |
| `finfact_000596` | 2008-10-02 | Blocked before network access: no contact-bearing SEC User-Agent. |
| `finfact_000786` | 2016-10-23 | Blocked before network access: no contact-bearing SEC User-Agent. |
| `finfact_001599` | 2021-06-22 | Blocked before network access: no contact-bearing SEC User-Agent. A prior retrieval attempt for this American Airlines claim recorded HTTP 403; it was not retried. |
| `finfact_002061` | 2009-03-18 | Blocked before network access: no contact-bearing SEC User-Agent. |

Consequently, the current run established no temporally valid SEC evidence.
The earlier HTTP 403 remains a source-access failure, not an unverifiable
prediction.

## Alpha Vantage supplementary-benchmark assessment

No supplementary benchmark was created because no candidate met the
claim-to-source validity requirement:

- The fixed sample has 0 claims applicable to the current Alpha Vantage
  retrieval path.
- A scan of the original 3,369 claims found explicit Target stock-policy
  claims, but they ask whether a policy caused a stock crash or decline.
  Alpha Vantage monthly prices are available for the 2016–2017 period, and
  Alpha Vantage symbol search confirmed `TGT` as Target Corp in the United
  States. Price history alone cannot establish that the policy caused a
  movement.
- The historical `NEWS_SENTIMENT` request for the relevant Target event window
  returned Alpha Vantage's premium-endpoint notice, not articles.
- The original broad-market/index claims do not identify a company equity;
  Alpha Vantage documents its index APIs as premium. Substituting a fund or
  guessing an index symbol would change the claim and would not be valid
  evidence.
- Alpha Vantage's daily compact endpoint covers only its latest 100 data
  points; its full daily history is premium-only. The monthly endpoint returned
  historical prices, but those records do not resolve the causal-claim
  limitation above. Endpoint access details were checked against the
  [Alpha Vantage API documentation](https://www.alphavantage.co/documentation/).

The source claims and their original labels remain untouched. No claims,
labels, evidence, or metrics were invented.

## Valid metrics

Only condition A has a valid completed sample for evaluation. It has 300
successful predictions aligned to the fixed benchmark IDs.

- Accuracy: **0.1900**
- Macro precision: **0.3116**
- Macro recall: **0.3409**
- Macro-F1: **0.1186**

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| REFUTED | 0.7500 | 0.0226 | 0.0438 |
| SUPPORTED | 0.0000 | 0.0000 | 0.0000 |
| UNVERIFIABLE | 0.1849 | 1.0000 | 0.3121 |

Confusion matrix (rows = gold label, columns = prediction):

| Gold \ Prediction | REFUTED | SUPPORTED | UNVERIFIABLE |
|---|---:|---:|---:|
| REFUTED | 3 | 4 | 126 |
| SUPPORTED | 1 | 0 | 112 |
| UNVERIFIABLE | 0 | 0 | 54 |

No B1, B2, or B3 evidence-grounded metrics are reported: each has zero
evidence-validated predictions. The invalid B2 successes and legacy B3 output
were excluded.

## Files and preservation

- A results: `condition_a_ollama_qwen25_3b_results.json`
- B1 results: `condition_b1_ollama_qwen25_3b_results.json`
- Preserved invalid B2 results/progress:
  `condition_b2_ollama_qwen25_3b_results.json` and
  `condition_b2_ollama_qwen25_3b_progress.json`
- B2 audit backup:
  `backups/condition_b2_pre_resume_20261011T133440Z/`
- Active B3 result path, `condition_b3_ollama_qwen25_3b_results.json`, remains
  absent.

The B2 result and progress files still hash-match the existing backup. A and B1
files were read-only during this run.

## Next action

To retry SEC retrieval for B3, configure `SEC_USER_AGENT` with the real
organization name and a legitimate contact email, then rerun only the
five-claim SEC preflight. Do not run B3 unless all applicable sources return
temporally valid evidence. B2 requires a separately defensible market-claim
sample and evidence that can test the claim semantics; current Alpha Vantage
access and these claims do not meet that requirement.
