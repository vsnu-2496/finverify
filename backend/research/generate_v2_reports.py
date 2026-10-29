#!/usr/bin/env python3
"""
generate_v2_reports.py

Independently validates and computes research metrics for Experiment v2:
- Condition A (Parametric baseline, N=300)
- Condition B1 (SEC EDGAR grounded, N=5 evaluated, 295 not applicable)
- Condition B2 (Alpha Vantage grounded, N=1 evaluated, 299 not applicable)
- Condition B3 (Combined SEC + Alpha Vantage grounded, N=6 evaluated, 294 not applicable)

Computes both full-sample metrics and paired comparison metrics against Condition A
on the exact subsets of applicable claims.

Outputs:
- backend/data/experiment_v2/consolidated_measured_report.json
- backend/data/experiment_v2/consolidated_comparison.csv
- backend/data/experiment_v2/consolidated_research_findings_report.md
"""

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
V2_DIR = DATA_DIR / "experiment_v2"
EVAL_PATH = DATA_DIR / "finfact_research_evaluation.json"

CLASSES = ["SUPPORTED", "REFUTED", "UNVERIFIABLE"]
LABEL_MAPPING = {
    "true": "SUPPORTED",
    "false": "REFUTED",
    "NEI": "UNVERIFIABLE",
}

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def calculate_metrics(gold_labels, predictions):
    """
    Computes accuracy, per-class precision/recall/F1, macro metrics, and confusion matrix.
    """
    n = len(gold_labels)
    if n == 0:
        return {
            "evaluated_claims": 0,
            "accuracy": None,
            "macro_precision": None,
            "macro_recall": None,
            "macro_f1": None,
            "per_class": {},
            "confusion_matrix": {},
            "predicted_class_counts": {c: 0 for c in CLASSES},
        }

    # Ensure gold labels are in SUPPORTED / REFUTED / UNVERIFIABLE format
    gold_mapped = [LABEL_MAPPING.get(g, g) for g in gold_labels]

    confusion = {g: {p: 0 for p in CLASSES} for g in CLASSES}
    for g, p in zip(gold_mapped, predictions):
        if g in CLASSES and p in CLASSES:
            confusion[g][p] += 1

    correct = sum(1 for g, p in zip(gold_mapped, predictions) if g == p)
    accuracy = correct / n

    per_class = {}
    for cls in CLASSES:
        tp = confusion[cls][cls]
        fp = sum(confusion[other][cls] for other in CLASSES if other != cls)
        fn = sum(confusion[cls][other] for other in CLASSES if other != cls)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[cls] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

    macro_prec = sum(per_class[c]["precision"] for c in CLASSES) / 3.0
    macro_rec = sum(per_class[c]["recall"] for c in CLASSES) / 3.0
    macro_f1 = sum(per_class[c]["f1"] for c in CLASSES) / 3.0

    return {
        "evaluated_claims": n,
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_prec, 4),
        "macro_recall": round(macro_rec, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "predicted_class_counts": {c: predictions.count(c) for c in CLASSES},
    }

def main():
    if not EVAL_PATH.exists():
        raise FileNotFoundError(f"Missing evaluation file: {EVAL_PATH}")
    eval_data = load_json(EVAL_PATH)
    gold_by_id = {item["claim_id"]: item["gold_label"] for item in eval_data}

    conditions_info = [
        ("A", "None (Internal Knowledge)", V2_DIR / "condition_a_ollama_qwen25_3b_results.json"),
        ("B1", "SEC", V2_DIR / "condition_b1_ollama_qwen25_3b_results.json"),
        ("B2", "Alpha Vantage", V2_DIR / "condition_b2_ollama_qwen25_3b_results.json"),
        ("B3", "SEC, Alpha Vantage", V2_DIR / "condition_b3_ollama_qwen25_3b_results.json"),
    ]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "qwen2.5:3b",
        "provider": "ollama",
        "dataset": "Fin-Fact 300-claim research sample",
        "experiment_version": "v2",
        "conditions": {},
        "paired_comparisons_against_condition_a": {},
        "evaluated_claim_details": [],
    }

    csv_rows = []

    # Store condition A predictions for paired evaluations
    cond_a_data = load_json(conditions_info[0][2])
    cond_a_preds_by_id = {r["claim_id"]: r["verdict"] for r in cond_a_data if r.get("verdict")}

    for cond_code, sources_desc, results_path in conditions_info:
        if not results_path.exists():
            print(f"Warning: {results_path} does not exist.")
            continue

        data = load_json(results_path)
        total_claims = len(data)
        successful_records = [r for r in data if r.get("status") == "success"]
        not_applicable_records = [r for r in data if r.get("status") == "not_applicable"]
        error_records = [r for r in data if r.get("status") == "error" and r.get("error")]

        evaluated_count = len(successful_records)
        gold_subset = [gold_by_id[r["claim_id"]] for r in successful_records]
        pred_subset = [r["verdict"] for r in successful_records]

        metrics = calculate_metrics(gold_subset, pred_subset)
        pred_dist = {c: pred_subset.count(c) for c in CLASSES}

        report["conditions"][cond_code] = {
            "condition": cond_code,
            "sources": sources_desc.split(", ") if sources_desc != "None (Internal Knowledge)" else ["(none - parametric only)"],
            "total_claims": total_claims,
            "evaluated_claims": evaluated_count,
            "not_applicable": len(not_applicable_records),
            "errors": len(error_records),
            "prediction_distribution": pred_dist,
            "metrics": metrics,
        }

        csv_rows.append({
            "Condition": cond_code,
            "Sources": sources_desc,
            "Total Sample": total_claims,
            "Evaluated Grounded": evaluated_count,
            "Not Applicable": len(not_applicable_records),
            "Errors": len(error_records),
            "Pred SUPPORTED": pred_dist["SUPPORTED"],
            "Pred REFUTED": pred_dist["REFUTED"],
            "Pred UNVERIFIABLE": pred_dist["UNVERIFIABLE"],
            "Accuracy": f"{metrics['accuracy']:.4f}" if metrics["accuracy"] is not None else "N/A",
            "Macro Precision": f"{metrics['macro_precision']:.4f}" if metrics["macro_precision"] is not None else "N/A",
            "Macro Recall": f"{metrics['macro_recall']:.4f}" if metrics["macro_recall"] is not None else "N/A",
            "Macro F1": f"{metrics['macro_f1']:.4f}" if metrics["macro_f1"] is not None else "N/A",
        })

        # Paired comparison against Condition A on the identical evaluated claims
        if cond_code != "A" and evaluated_count > 0:
            paired_ids = [r["claim_id"] for r in successful_records]
            paired_gold = [gold_by_id[cid] for cid in paired_ids]
            paired_a_preds = [cond_a_preds_by_id[cid] for cid in paired_ids]
            paired_b_preds = pred_subset

            paired_metrics_a = calculate_metrics(paired_gold, paired_a_preds)
            paired_metrics_b = metrics

            report["paired_comparisons_against_condition_a"][cond_code] = {
                "evaluated_claim_ids": paired_ids,
                "n_paired": len(paired_ids),
                "condition_a_paired_metrics": paired_metrics_a,
                f"condition_{cond_code.lower()}_paired_metrics": paired_metrics_b,
                "delta_accuracy": round(paired_metrics_b["accuracy"] - paired_metrics_a["accuracy"], 4),
                "delta_macro_f1": round(paired_metrics_b["macro_f1"] - paired_metrics_a["macro_f1"], 4),
            }

    # Extract all evaluated claims from B3 (the union of B1 and B2)
    b3_data = load_json(conditions_info[3][2])
    for r in b3_data:
        if r.get("status") == "success":
            cid = r["claim_id"]
            report["evaluated_claim_details"].append({
                "claim_id": cid,
                "claim_text": r.get("claim_text"),
                "claim_date": r.get("claim_date"),
                "gold_label": gold_by_id.get(cid),
                "condition_a_pred": cond_a_preds_by_id.get(cid),
                "condition_b3_pred": r.get("verdict"),
                "confidence": r.get("confidence"),
                "explanation": r.get("explanation"),
                "evidence": r.get("evidence", []),
                "evidence_sources": [e.get("source") for e in r.get("evidence", [])],
            })

    # Save JSON report
    report_json_path = V2_DIR / "consolidated_measured_report.json"
    save_json(report_json_path, report)
    print(f"Saved: {report_json_path}")

    # Save CSV comparison
    report_csv_path = V2_DIR / "consolidated_comparison.csv"
    with report_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Saved: {report_csv_path}")

    # Generate Markdown summary report
    md_path = V2_DIR / "consolidated_research_findings_report.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("# Research Findings: Evidence-Grounded vs Internal-Knowledge Verification (v2)\n\n")
        f.write("**Research Title:** Evidence-Grounded vs. Internal-Knowledge Verification: A Comparative Study of LLM Misinformation Detection in Financial News  \n")
        f.write("**Model:** Ollama `qwen2.5:3b`  \n")
        f.write(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  \n")
        f.write("**Dataset:** Fin-Fact fixed 300-claim research sample (seed 42)  \n\n")

        f.write("## 1. Summary of Overall Metrics across Conditions\n\n")
        f.write("| Condition | Sources | Total Sample | Evaluated Grounded | Not Applicable | Errors | Accuracy | Macro F1 |\n")
        f.write("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for row in csv_rows:
            f.write(f"| **{row['Condition']}** | {row['Sources']} | {row['Total Sample']} | {row['Evaluated Grounded']} | {row['Not Applicable']} | {row['Errors']} | {row['Accuracy']} | {row['Macro F1']} |\n")

        f.write("\n## 2. Paired Subset Comparisons against Condition A Baseline\n\n")
        f.write("To ensure scientific validity, grounded models are evaluated directly against the internal-knowledge baseline on the exact same claims where evidence was applicable:\n\n")
        for cond_code, paired in report["paired_comparisons_against_condition_a"].items():
            a_acc = paired["condition_a_paired_metrics"]["accuracy"]
            b_acc = paired[f"condition_{cond_code.lower()}_paired_metrics"]["accuracy"]
            a_f1 = paired["condition_a_paired_metrics"]["macro_f1"]
            b_f1 = paired[f"condition_{cond_code.lower()}_paired_metrics"]["macro_f1"]
            n = paired["n_paired"]
            f.write(f"### Condition {cond_code} vs Condition A (N = {n})\n")
            f.write(f"- **Evaluated Claims:** `{', '.join(paired['evaluated_claim_ids'])}`\n")
            f.write(f"- **Condition A (Internal Knowledge):** Accuracy = {a_acc:.4f}, Macro-F1 = {a_f1:.4f}\n")
            f.write(f"- **Condition {cond_code} (Grounded):** Accuracy = {b_acc:.4f}, Macro-F1 = {b_f1:.4f}\n")
            f.write(f"- **Delta:** Accuracy: {paired['delta_accuracy']:+.4f}, Macro-F1: {paired['delta_macro_f1']:+.4f}\n\n")

        f.write("## 3. Detail of Evaluated Claims and Retrieved Grounding Evidence\n\n")
        for item in report["evaluated_claim_details"]:
            f.write(f"### Claim `{item['claim_id']}` ({', '.join(item['evidence_sources'])})\n")
            f.write(f"- **Claim:** \"{item['claim_text']}\" (Date: {item['claim_date']})\n")
            f.write(f"- **Gold Label:** `{item['gold_label']}` | **Condition A Pred:** `{item['condition_a_pred']}` | **Grounded B3 Pred:** `{item['condition_b3_pred']}` (Confidence: {item['confidence']})\n")
            f.write(f"- **Model Explanation:** {item['explanation']}\n")
            f.write("- **Evidence Sources & Excerpts:**\n")
            for ev in item.get("evidence", []):
                url = ev.get("url") or ev.get("source")
                snip = ev.get("snippet") or ev.get("data") or ev.get("quote") or str(ev)
                clean_snip = str(snip).replace('\n', ' ')[:300]
                f.write(f"  - **Source/URL:** {url}\n")
                f.write(f"  - **Excerpt/Data:** *\"{clean_snip}...\"*\n")
            f.write("\n")

    print(f"Saved: {md_path}")

if __name__ == "__main__":
    main()
