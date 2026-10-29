"""Generate the reproducible report for the local demonstration artifacts."""

import csv
import json
from pathlib import Path

FINAL_DIR = Path(__file__).resolve().parent / "results" / "final_demo"
NOTE = "These demonstration results are produced by a deterministic fallback verifier because the Gemini API free-tier quota was exhausted. They are intended to validate the experimental software pipeline and visualization, not to represent measured LLM performance."


def generate_report():
    a = json.loads((FINAL_DIR / "condition_a_demo_75.json").read_text(encoding="utf-8"))
    b = json.loads((FINAL_DIR / "condition_b_demo_75.json").read_text(encoding="utf-8"))
    rows = []
    sources = [("A_INTERNAL_KNOWLEDGE", a["metrics"])]
    sources.extend((variant, value["metrics"]) for variant, value in b["variants"].items())
    for condition, metrics in sources:
        rows.append({
            "condition": condition,
            "run_mode": "DEMO_FALLBACK",
            "accuracy": metrics["accuracy"],
            "precision": metrics["macro_precision"],
            "recall": metrics["macro_recall"],
            "macro_f1": metrics["macro_f1"],
            "supported_f1": metrics["per_class"]["SUPPORTED"]["f1"],
            "refuted_f1": metrics["per_class"]["REFUTED"]["f1"],
            "unverifiable_f1": metrics["per_class"]["UNVERIFIABLE"]["f1"],
        })
    comparison = {"run_mode": "DEMO_FALLBACK", "rows": rows, "note": NOTE}
    (FINAL_DIR / "comparison_demo_75.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    with (FINAL_DIR / "comparison_demo_75.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    report = f"""# Evidence-Grounded vs. Internal-Knowledge Verification

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
{chr(10).join(f"- **{row['condition']}**: accuracy {row['accuracy']:.4f}, macro F1 {row['macro_f1']:.4f}" for row in rows)}

## 9. Comparison
The full comparison is stored in `comparison_demo_75.json` and `comparison_demo_75.csv`. Differences here do not establish that evidence improves LLM performance because no real LLM predictions were produced.

## 10. Limitations
- {NOTE}
- Real Gemini execution requires available API quota.
- Synthetic evidence is not external financial evidence.
- Demo fallback output must not be presented as measured LLM performance.
- User-uploaded articles do not contribute to Fin-Fact research accuracy.

## 11. Reproducibility
Run `python -m research.run_condition_a_demo` and `python -m research.run_condition_b_demo` from `backend`. The dataset, label mapping, seed, pilot IDs, and deterministic rules remain fixed.

## 12. Future work
Repeat the same pilot in REAL_LLM mode after quota is available, then compare conditions using the unchanged claim IDs, dates, prompts, and leakage controls.
"""
    (FINAL_DIR / "research_report.md").write_text(report, encoding="utf-8")
    return comparison, FINAL_DIR / "research_report.md"


if __name__ == "__main__":
    comparison, report_path = generate_report()
    print(json.dumps({"rows": comparison["rows"], "report": str(report_path)}, indent=2))
