# Demo Results

These artifacts are **DEMO_FALLBACK** results. They are produced by deterministic local Python rules because the Gemini API free-tier quota is exhausted. They are intended to validate the experimental software pipeline and visualization, not to represent measured LLM performance.

- The same fixed 75 Fin-Fact pilot claims are used for Conditions A and B.
- Fin-Fact gold labels are used only after prediction generation for evaluation.
- The verifier receives only `claim_id`, `claim_text`, and `claim_date`.
- Condition A uses no evidence.
- Condition B uses synthetic local SEC-style, market-data-style, and combined evidence.
- Synthetic evidence is not real SEC, Alpha Vantage, or web evidence.
- No Gemini, SEC EDGAR, Alpha Vantage, or web requests are made in demo mode.
- User-uploaded articles are separate demonstration inputs and do not affect Fin-Fact metrics.

Run from `backend`:

```powershell
$env:RESEARCH_MODE="demo"
python -m research.run_condition_a_demo
python -m research.run_condition_b_demo
python -m research.generate_report
```

The files in this directory are reproducible from the unchanged dataset and fixed pilot selection. Demo metrics must not be reported as real LLM performance or as evidence that external evidence improves verification.
