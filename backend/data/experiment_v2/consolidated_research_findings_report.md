# Research Findings: Evidence-Grounded vs Internal-Knowledge Verification (v2)

**Research Title:** Evidence-Grounded vs. Internal-Knowledge Verification: A Comparative Study of LLM Misinformation Detection in Financial News  
**Model:** Ollama `qwen2.5:3b`  
**Date:** 2026-10-19 17:31 UTC  
**Dataset:** Fin-Fact fixed 300-claim research sample (seed 42)  

## 1. Summary of Overall Metrics across Conditions

| Condition | Sources | Total Sample | Evaluated Grounded | Not Applicable | Errors | Accuracy | Macro F1 |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | None (Internal Knowledge) | 300 | 300 | 0 | 0 | 0.1900 | 0.1186 |
| **B1** | SEC | 300 | 5 | 295 | 0 | 0.4000 | 0.1905 |
| **B2** | Alpha Vantage | 300 | 1 | 299 | 0 | 0.0000 | 0.0000 |
| **B3** | SEC, Alpha Vantage | 300 | 6 | 294 | 0 | 0.3333 | 0.1667 |

## 2. Paired Subset Comparisons against Condition A Baseline

To ensure scientific validity, grounded models are evaluated directly against the internal-knowledge baseline on the exact same claims where evidence was applicable:

### Condition B1 vs Condition A (N = 5)
- **Evaluated Claims:** `finfact_000462, finfact_000596, finfact_000786, finfact_001599, finfact_002061`
- **Condition A (Internal Knowledge):** Accuracy = 0.4000, Macro-F1 = 0.1905
- **Condition B1 (Grounded):** Accuracy = 0.4000, Macro-F1 = 0.1905
- **Delta:** Accuracy: +0.0000, Macro-F1: +0.0000

### Condition B2 vs Condition A (N = 1)
- **Evaluated Claims:** `finfact_002666`
- **Condition A (Internal Knowledge):** Accuracy = 0.0000, Macro-F1 = 0.0000
- **Condition B2 (Grounded):** Accuracy = 0.0000, Macro-F1 = 0.0000
- **Delta:** Accuracy: +0.0000, Macro-F1: +0.0000

### Condition B3 vs Condition A (N = 6)
- **Evaluated Claims:** `finfact_000462, finfact_000596, finfact_000786, finfact_001599, finfact_002061, finfact_002666`
- **Condition A (Internal Knowledge):** Accuracy = 0.3333, Macro-F1 = 0.1667
- **Condition B3 (Grounded):** Accuracy = 0.3333, Macro-F1 = 0.1667
- **Delta:** Accuracy: +0.0000, Macro-F1: +0.0000

## 3. Detail of Evaluated Claims and Retrieved Grounding Evidence

### Claim `finfact_000462` (SEC, SEC)
- **Claim:** "Are Costco shutting down stores throughout the country?" (Date: 2021-02-10)
- **Gold Label:** `false` | **Condition A Pred:** `UNVERIFIABLE` | **Grounded B3 Pred:** `UNVERIFIABLE` (Confidence: 0.7)
- **Model Explanation:** The provided evidence does not contain any information related to Costco's store closures or shutdowns.
- **Evidence Sources & Excerpts:**
  - **Source/URL:** https://www.sec.gov/Archives/edgar/data/909832/000119312521017361/d115093d8k.htm
  - **Excerpt/Data:** *"{'source': 'SEC', 'evidence_text': '8-K UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, D.C. 20549 FORM 8-K CURRENT REPORT Pursuant to Section 13 or 15(d) of the Securities Exchange Act of 1934 Date of Report (Date of Earliest Event Reported): January 21, 2021 COSTCO WHOLESALE CORPORATI..."*
  - **Source/URL:** https://www.sec.gov/Archives/edgar/data/909832/000119312521016502/d100960d8k.htm
  - **Excerpt/Data:** *"{'source': 'SEC', 'evidence_text': '8-K UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, D.C. 20549 FORM 8-K CURRENT REPORT Pursuant to Section 13 or 15(d) of the Securities Exchange Act of 1934 Date of Report (Date of Earliest Event Reported): January 21, 2021 COSTCO WHOLESALE CORPORATI..."*

### Claim `finfact_000596` (SEC, SEC)
- **Claim:** "Fannie Mae is loosening credit standards in order to assist in providing mortgage loans." (Date: 2008-10-02)
- **Gold Label:** `NEI` | **Condition A Pred:** `UNVERIFIABLE` | **Grounded B3 Pred:** `UNVERIFIABLE` (Confidence: 0.7)
- **Model Explanation:** The provided evidence does not contain any information related to Fannie Mae's credit standards or any actions taken to assist in providing mortgage loans.
- **Evidence Sources & Excerpts:**
  - **Source/URL:** https://www.sec.gov/Archives/edgar/data/310522/000129993308004619/htm_29249.htm
  - **Excerpt/Data:** *"{'source': 'SEC', 'evidence_text': 'ations pursuant to Rule 14d-2(b) under the Exchange Act (17 CFR 240.14d-2(b)) [ ] Pre-commencement communications pursuant to Rule 13e-4(c) under the Exchange Act (17 CFR 240.13e-4(c)) Top of the Form Item 5.02 Departure of Directors or Certain Officers; Election ..."*
  - **Source/URL:** https://www.sec.gov/Archives/edgar/data/310522/000129993308004533/htm_29162.htm
  - **Excerpt/Data:** *"{'source': 'SEC', 'evidence_text': 'shall not be deemed "filed" for purposes of Section 18 of the Securities Exchange Act of 1934, or otherwise subject to the liabilities of Section 18, nor shall it be deemed incorporated by reference into any disclosure document relating to Fannie Mae, except to th..."*

### Claim `finfact_000786` (SEC, SEC)
- **Claim:** "Ford is moving all of their small-car production to Mexico." (Date: 2016-10-23)
- **Gold Label:** `true` | **Condition A Pred:** `UNVERIFIABLE` | **Grounded B3 Pred:** `UNVERIFIABLE` (Confidence: 0.0)
- **Model Explanation:** The provided evidence does not contain any information regarding Ford's production plans or relocation of small-car production to Mexico.
- **Evidence Sources & Excerpts:**
  - **Source/URL:** https://www.sec.gov/Archives/edgar/data/37996/000003799616000153/sales8-kdated10x3x2016.htm
  - **Excerpt/Data:** *"{'source': 'SEC', 'evidence_text': '8-K 1 sales8-kdated10x3x2016.htm 8-K Document UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, D. C. 20549 FORM 8-K CURRENT REPORT Pursuant to Section 13 or 15(d) of the Securities Exchange Act of 1934 Date of Report: October 3, 2016 (Date of earliest ..."*
  - **Source/URL:** https://www.sec.gov/Archives/edgar/data/37996/000003799616000151/investorday8-kdated9x14x20.htm
  - **Excerpt/Data:** *"{'source': 'SEC', 'evidence_text': '8-K 1 investorday8-kdated9x14x20.htm 8-K Document UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, D. C. 20549 FORM 8-K CURRENT REPORT Pursuant to Section 13 or 15(d) of the Securities Exchange Act of 1934 Date of Report: September 14, 2016 (Date of ea..."*

### Claim `finfact_001599` (SEC, SEC)
- **Claim:** "Did American Airlines Receive Billions in Federal Aid Then Lay Off 30,000 Employees?" (Date: 2021-06-22)
- **Gold Label:** `NEI` | **Condition A Pred:** `UNVERIFIABLE` | **Grounded B3 Pred:** `UNVERIFIABLE` (Confidence: 0.0)
- **Model Explanation:** The provided evidence does not contain any specific information regarding the amount of federal aid received by American Airlines or any details about layoffs.
- **Evidence Sources & Excerpts:**
  - **Source/URL:** https://www.sec.gov/Archives/edgar/data/6201/000000620121000066/aal-20210610.htm
  - **Excerpt/Data:** *"{'source': 'SEC', 'evidence_text': 'aal-20210610 UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, D.C. 20549 FORM 8-K CURRENT REPORT Pursuant to Section 13 or 15(d) of the Securities Exchange Act of 1934 Date of Report (Date of earliest event reported): June 10, 2021 AMERICAN AIRLINES GR..."*
  - **Source/URL:** https://www.sec.gov/Archives/edgar/data/6201/000000620121000063/aal-20210609.htm
  - **Excerpt/Data:** *"{'source': 'SEC', 'evidence_text': 'aal-20210609 UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, D.C. 20549 FORM 8-K CURRENT REPORT Pursuant to Section 13 or 15(d) of the Securities Exchange Act of 1934 Date of Report (Date of earliest event reported): June 9, 2021 AMERICAN AIRLINES GRO..."*

### Claim `finfact_002061` (SEC, SEC)
- **Claim:** "We had bipartisan legislation that got through the Senate that would have prevented bonuses like AIG's and then somehow mysteriously disappeared." (Date: 2009-03-18)
- **Gold Label:** `true` | **Condition A Pred:** `UNVERIFIABLE` | **Grounded B3 Pred:** `UNVERIFIABLE` (Confidence: 0.7)
- **Model Explanation:** The supplied evidence does not contain any information related to bipartisan legislation, AIG's bonuses, or the disappearance of such legislation.
- **Evidence Sources & Excerpts:**
  - **Source/URL:** https://www.sec.gov/Archives/edgar/data/5272/000095012309004097/y75051e8vk.htm
  - **Excerpt/Data:** *"{'source': 'SEC', 'evidence_text': '-commencement communications pursuant to Rule 13e4(c) under the Exchange Act (17 CFR 240.13e-4(c)) Section 3 — Securities and Trading Markets Item 3.02. Unregistered Sales of Equity Securities. On March 4, 2009, American International Group, Inc. (AIG) issued and ..."*
  - **Source/URL:** https://www.sec.gov/Archives/edgar/data/5272/000095012309003734/y74794e10vk.htm
  - **Excerpt/Data:** *"{'source': 'SEC', 'evidence_text': 'in certain geographic locations to fall, resulting in impairment charges on real estate held for investment purposes. Liquidity issues at AIG parent and lower asset performance as a result of challenging market conditions have contributed to the loss of institutio..."*

### Claim `finfact_002666` (Alpha Vantage)
- **Claim:** "Did Trump Tweet That If 'Dow Joans' Tanked, the President Should Be Shot Out of a Cannon?" (Date: 2018-02-05)
- **Gold Label:** `false` | **Condition A Pred:** `UNVERIFIABLE` | **Grounded B3 Pred:** `UNVERIFIABLE` (Confidence: 0.7)
- **Model Explanation:** The provided evidence contains Dow Jones Industrial Average (DIA) monthly market data and does not mention any tweet by Trump regarding stock market performance or any specific action in case of a stock market drop.
- **Evidence Sources & Excerpts:**
  - **Source/URL:** https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY&symbol=DIA
  - **Excerpt/Data:** *"{'source': 'Alpha Vantage', 'evidence_text': 'Dow Jones Industrial Average (DIA) monthly market data for period ending 2018-01-31 (claim date 2018-02-05): open 248.34, high 265.93, low 247.23, close 261.44, volume 102220886 (1-month change: +5.68% vs 2017-12-29 close 247.38).', 'evidence_date': '201..."*

