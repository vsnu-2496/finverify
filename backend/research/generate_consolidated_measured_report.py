import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from research.config import CLASSES, LABEL_MAPPING
from research.run_openai_experiment_300 import (
    CONDITION_CONFIGS,
    EVALUATION_PATH,
    SAMPLE_PATH,
    _calculate_metrics,
)

DATA_DIR = BACKEND_DIR / "data"
OUTPUT_DIR = DATA_DIR / "final_experiment"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

eval_data = json.load(open(EVALUATION_PATH, encoding="utf-8"))
gold_by_id = {r["claim_id"]: r["gold_label"] for r in eval_data}

consolidated = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "model": "qwen2.5:3b",
    "provider": "ollama",
    "dataset": "Fin-Fact 300-claim research sample",
    "conditions": {},
}

table_rows = []

for cond_name, config in CONDITION_CONFIGS.items():
    res_path = config["result_path"]
    prog_path = config["progress_path"]
    rows = json.load(open(res_path, encoding="utf-8"))
    
    total = len(rows)
    success = sum(1 for r in rows if r.get("status") == "success")
    not_applicable = sum(1 for r in rows if r.get("status") == "not_applicable")
    errors = sum(1 for r in rows if r.get("status") == "error" and r.get("error"))
    
    metrics = _calculate_metrics(rows, gold_by_id)
    
    pred_counts = {cls: sum(1 for r in rows if r.get("verdict") == cls) for cls in CLASSES}
    
    cond_record = {
        "condition": cond_name,
        "sources": list(config["sources"]) or ["(none - parametric only)"],
        "total_claims": total,
        "evaluated_claims": success,
        "not_applicable": not_applicable,
        "errors": errors,
        "prediction_distribution": pred_counts,
        "metrics": metrics,
    }
    consolidated["conditions"][cond_name] = cond_record
    
    acc = f"{metrics.get('accuracy', 0.0):.4f}" if success > 0 else "N/A"
    prec = f"{metrics.get('macro_precision', 0.0):.4f}" if success > 0 else "N/A"
    rec = f"{metrics.get('macro_recall', 0.0):.4f}" if success > 0 else "N/A"
    f1 = f"{metrics.get('macro_f1', 0.0):.4f}" if success > 0 else "N/A"
    
    table_rows.append([
        cond_name,
        ", ".join(config["sources"]) or "None (Internal Knowledge)",
        total,
        success,
        not_applicable,
        errors,
        pred_counts.get("SUPPORTED", 0),
        pred_counts.get("REFUTED", 0),
        pred_counts.get("UNVERIFIABLE", 0),
        acc,
        prec,
        rec,
        f1,
    ])

# Methodological Notes & Comparative Scope Warnings
consolidated["methodological_notes"] = {
    "sample_comparability_warning": (
        "Condition A evaluates the full n=300 parametric baseline. Conditions B1 and B3 evaluate only the n=5 subset "
        "where corporate regulatory filings were applicable and retrieved. Condition B2 evaluated n=0 claims because the "
        "benchmark contains 0 company equity stock-movement claims. Therefore, the 40.0% accuracy on the 5-claim subset "
        "in B1/B3 cannot be statistically or scientifically compared against the 19.0% accuracy on the full 300-claim "
        "dataset to claim general performance improvement."
    ),
    "semantic_relevance_finding": (
        "Audit of the 5 retrieved SEC EDGAR filings indicates that while filings are temporally valid and match the identified "
        "corporate registrants, formal regulatory disclosures (Forms 10-K and 8-K) do not contain assertions regarding viral "
        "internet rumors, store closure rumors, or congressional procedural debates. In all 5 cases, the model recognized this "
        "semantic insufficiency and appropriately concluded UNVERIFIABLE."
    ),
    "alpha_vantage_limitation": (
        "Alpha Vantage GLOBAL_QUOTE returns current trading day quotes, which are rejected for historical claims by the "
        "temporal validity safeguard. Furthermore, Fin-Fact contains 0 equity price movement claims matching Alpha Vantage capabilities."
    ),
}

# Save JSON
json_out = OUTPUT_DIR / "consolidated_measured_report.json"
json_out.write_text(json.dumps(consolidated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# Save CSV
csv_out = OUTPUT_DIR / "consolidated_comparison.csv"
with csv_out.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Condition", "Sources", "Total Sample", "Evaluated Grounded", "Not Applicable",
        "Errors", "Pred SUPPORTED", "Pred REFUTED", "Pred UNVERIFIABLE",
        "Accuracy", "Macro Precision", "Macro Recall", "Macro F1"
    ])
    writer.writerows(table_rows)

# Save Markdown Summary
md_out = OUTPUT_DIR / "consolidated_research_findings_report.md"
md_lines = [
    "# Consolidated Research Findings & Audit Report",
    "",
    "**Generated:** " + consolidated["generated_at"],
    "**Model:** " + consolidated["model"] + " (local Ollama)",
    "**Benchmark:** " + consolidated["dataset"],
    "",
    "## 1. Experimental Conditions Measured Outcomes",
    "",
    "| Condition | Sources | Total Sample | Evaluated Grounded | Not Applicable | Errors | Accuracy | Macro-F1 |",
    "|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
]
for r in table_rows:
    md_lines.append(f"| **{r[0]}** | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[9]} | {r[12]} |")

md_lines.extend([
    "",
    "## 2. Methodological Findings & Comparability Limitations",
    "",
    "> [!WARNING]",
    "> **Non-Comparable Sample Sizes:** The 40.0% accuracy on the 5-claim grounded subset in B1 and B3 cannot be directly compared against the 19.0% baseline accuracy on the full 300-claim Condition A sample. No claim should be made that evidence grounding improves overall accuracy on Fin-Fact.",
    "",
    "### Key Audited Insights",
    "1. **Parametric Memory (Condition A):** The ungrounded 3B model abstained (UNVERIFIABLE) on 292/300 claims (97.3%), achieving 19.0% accuracy due to lack of specific factual recall.",
    "2. **Regulatory SEC Grounding (Condition B1 & B3):** Successfully retrieved temporally valid 10-K/8-K filings for the 5 corporate claims. However, formal corporate disclosures do not address viral rumors or political debates, leading the model to accurately identify the evidence as insufficient (UNVERIFIABLE) in all 5 cases.",
    "3. **Market Data Grounding (Condition B2):** 0 of 300 claims qualified as company stock movement claims. Alpha Vantage returned 0 grounded claims and 300 not applicable records, preventing any fabricated quotes or predictions.",
    "",
])
md_out.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

print("=== CONSOLIDATED MEASURED REPORT ===")
print(f"Saved JSON: {json_out}")
print(f"Saved CSV:  {csv_out}")
print(f"Saved MD:   {md_out}\n")
print(f"{'Cond':<5} | {'Sources':<30} | {'Total':<5} | {'Eval':<5} | {'N/A':<5} | {'Err':<4} | {'Supp':<4} | {'Ref':<4} | {'Unver':<5} | {'Acc':<7} | {'Macro-F1':<8}")
print("-" * 105)
for r in table_rows:
    print(f"{r[0]:<5} | {r[1]:<30} | {r[2]:<5} | {r[3]:<5} | {r[4]:<5} | {r[5]:<4} | {r[6]:<4} | {r[7]:<4} | {r[8]:<5} | {r[9]:<7} | {r[12]:<8}")
