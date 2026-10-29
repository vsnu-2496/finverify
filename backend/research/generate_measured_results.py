"""Generate audited metrics and vector graphs from saved Ollama results."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from research.config import CLASSES
from research.run_openai_experiment_300 import (
    CONDITION_CONFIGS,
    EVALUATION_PATH,
    SAMPLE_PATH,
    _calculate_metrics,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT_DIR = DATA_DIR / "final_experiment"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
COLORS = {
    "SUPPORTED": "#1976D2",
    "REFUTED": "#D55E00",
    "UNVERIFIABLE": "#6B7280",
}


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _svg_start(title, description, width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{escape(title)}</title>",
        f"<desc id=\"desc\">{escape(description)}</desc>",
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#17212B}.title{font-size:25px;font-weight:700}.subtitle{font-size:14px;fill:#52606D}.label{font-size:15px}.small{font-size:12px;fill:#52606D}.value{font-size:14px;font-weight:700}</style>',
    ]


def _save_svg(filename, lines):
    lines.append("</svg>")
    (OUTPUT_DIR / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _overview_svg(metrics):
    width, height = 1000, 560
    lines = _svg_start(
        "Condition A measured performance",
        "Accuracy, macro precision, macro recall, and macro F1 computed from 300 saved Condition A predictions.",
        width,
        height,
    )
    lines.extend([
        '<text class="title" x="70" y="58">Condition A — measured performance</text>',
        '<text class="subtitle" x="70" y="86">Fin-Fact fixed sample · Ollama qwen2.5:3b · n = 300 · metrics from saved predictions</text>',
    ])
    values = [
        ("Accuracy", metrics["accuracy"], "#0072B2"),
        ("Macro precision", metrics["macro_precision"], "#009E73"),
        ("Macro recall", metrics["macro_recall"], "#E69F00"),
        ("Macro-F1", metrics["macro_f1"], "#CC79A7"),
    ]
    left, top, chart_width, chart_height = 275, 135, 610, 325
    for tick in range(0, 6):
        value = tick / 5
        x = left + chart_width * value
        lines.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + chart_height}" stroke="#DCE2E8" stroke-width="1"/>')
        lines.append(f'<text class="small" x="{x}" y="{top + chart_height + 25}" text-anchor="middle">{value:.1f}</text>')
    for index, (label, value, color) in enumerate(values):
        y = top + 27 + index * 76
        bar_width = chart_width * value
        lines.append(f'<text class="label" x="{left - 18}" y="{y + 22}" text-anchor="end">{escape(label)}</text>')
        lines.append(f'<rect x="{left}" y="{y}" width="{bar_width:.2f}" height="34" rx="4" fill="{color}"/>')
        lines.append(f'<text class="value" x="{left + bar_width + 10:.2f}" y="{y + 22}">{value:.4f}</text>')
    lines.extend([
        f'<text class="small" x="{left + chart_width / 2}" y="{top + chart_height + 58}" text-anchor="middle">Score (0–1)</text>',
        '<text class="subtitle" x="70" y="525">No B-condition measurements are plotted: saved evidence-grounded predictions failed evidence validation.</text>',
    ])
    _save_svg("condition_a_overview.svg", lines)


def _class_metrics_svg(metrics):
    width, height = 1100, 590
    lines = _svg_start(
        "Condition A per-class metrics",
        "Grouped bars show precision, recall, and F1 for the three benchmark classes.",
        width,
        height,
    )
    lines.extend([
        '<text class="title" x="70" y="58">Condition A — per-class metrics</text>',
        '<text class="subtitle" x="70" y="86">Zero-denominator precision or recall is reported as 0, following the project evaluator.</text>',
    ])
    left, top, chart_width, chart_height = 300, 145, 650, 330
    for tick in range(0, 6):
        value = tick / 5
        x = left + chart_width * value
        lines.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + chart_height}" stroke="#DCE2E8" stroke-width="1"/>')
        lines.append(f'<text class="small" x="{x}" y="{top + chart_height + 24}" text-anchor="middle">{value:.1f}</text>')
    metric_names = ("precision", "recall", "f1")
    metric_colors = {"precision": "#0072B2", "recall": "#009E73", "f1": "#CC79A7"}
    for class_index, class_name in enumerate(CLASSES):
        group_top = top + class_index * 108
        lines.append(f'<text class="label" x="{left - 18}" y="{group_top + 49}" text-anchor="end">{escape(class_name.title())}</text>')
        for metric_index, metric_name in enumerate(metric_names):
            value = metrics["per_class"][class_name][metric_name]
            y = group_top + metric_index * 27
            bar_width = chart_width * value
            lines.append(f'<rect x="{left}" y="{y}" width="{bar_width:.2f}" height="18" rx="3" fill="{metric_colors[metric_name]}"/>')
            lines.append(f'<text class="small" x="{left + bar_width + 8:.2f}" y="{y + 14}">{value:.4f}</text>')
    legend_x = 370
    for index, metric_name in enumerate(metric_names):
        x = legend_x + index * 190
        lines.append(f'<rect x="{x}" y="525" width="16" height="16" rx="2" fill="{metric_colors[metric_name]}"/>')
        lines.append(f'<text class="small" x="{x + 24}" y="538">{metric_name.title()}</text>')
    _save_svg("condition_a_per_class_metrics.svg", lines)


def _confusion_svg(metrics):
    width, height = 900, 650
    lines = _svg_start(
        "Condition A confusion matrix",
        "Confusion matrix for the 300 saved Condition A predictions; rows are gold classes and columns are predicted classes.",
        width,
        height,
    )
    lines.extend([
        '<text class="title" x="65" y="58">Condition A — confusion matrix</text>',
        '<text class="subtitle" x="65" y="86">Rows: gold label · columns: predicted label · n = 300</text>',
    ])
    x0, y0, cell_w, cell_h = 320, 190, 165, 100
    max_value = max(max(metrics["confusion_matrix"][actual].values()) for actual in CLASSES) or 1
    lines.append(f'<text class="label" x="{x0 + 1.5 * cell_w}" y="135" text-anchor="middle">Predicted label</text>')
    lines.append(f'<text class="label" x="105" y="{y0 + 1.5 * cell_h}" text-anchor="middle" transform="rotate(-90 105 {y0 + 1.5 * cell_h})">Gold label</text>')
    for col, predicted in enumerate(CLASSES):
        label = predicted.replace("UNVERIFIABLE", "UNVERIFIABLE")
        lines.append(f'<text class="small" x="{x0 + col * cell_w + cell_w / 2}" y="{y0 - 16}" text-anchor="middle">{escape(label)}</text>')
    for row, actual in enumerate(CLASSES):
        lines.append(f'<text class="small" x="{x0 - 18}" y="{y0 + row * cell_h + cell_h / 2 + 5}" text-anchor="end">{escape(actual)}</text>')
        for col, predicted in enumerate(CLASSES):
            value = metrics["confusion_matrix"][actual][predicted]
            alpha = 0.08 + 0.72 * value / max_value
            x, y = x0 + col * cell_w, y0 + row * cell_h
            lines.append(f'<rect x="{x}" y="{y}" width="{cell_w - 4}" height="{cell_h - 4}" fill="#0072B2" fill-opacity="{alpha:.3f}" stroke="#FFFFFF" stroke-width="2"/>')
            color = "#FFFFFF" if value / max_value > 0.48 else "#17212B"
            lines.append(f'<text x="{x + cell_w / 2 - 2}" y="{y + cell_h / 2 + 9}" text-anchor="middle" font-size="26" font-weight="700" style="fill:{color}">{value}</text>')
    lines.append('<text class="small" x="320" y="540">Cell color intensity scales with count; values are printed in each cell.</text>')
    _save_svg("condition_a_confusion_matrix.svg", lines)


def generate():
    sample = _read_json(SAMPLE_PATH)
    evaluation = _read_json(EVALUATION_PATH)
    results_path = CONDITION_CONFIGS["A"]["result_path"]
    results = _read_json(results_path)
    sample_ids = [item["claim_id"] for item in sample]
    evaluation_ids = [item["claim_id"] for item in evaluation]
    result_ids = [item["claim_id"] for item in results]
    if len(sample_ids) != 300 or len(set(sample_ids)) != 300:
        raise ValueError("The fixed sample must contain 300 unique claim IDs")
    if evaluation_ids != sample_ids or result_ids != sample_ids:
        raise ValueError("Sample, evaluation, and Condition A result IDs must align in order")
    if any(item.get("status") != "success" or item.get("verdict") not in CLASSES for item in results):
        raise ValueError("Condition A contains incomplete or invalid predictions")

    gold_by_id = {item["claim_id"]: item["gold_label"] for item in evaluation}
    gold_labels = {
        "true": "SUPPORTED",
        "false": "REFUTED",
        "NEI": "UNVERIFIABLE",
    }
    metrics = _calculate_metrics(results, gold_by_id)
    if metrics["evaluated_claims"] != 300:
        raise ValueError("Expected exactly 300 evaluated Condition A predictions")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _overview_svg(metrics)
    _class_metrics_svg(metrics)
    _confusion_svg(metrics)

    condition_summary = {}
    for condition in ("B1", "B2", "B3"):
        path = CONDITION_CONFIGS[condition]["result_path"]
        if not path.exists():
            condition_summary[condition] = {"result_file_exists": False, "valid_evidence_predictions": 0}
            continue
        rows = _read_json(path)
        evidence_predictions = sum(
            item.get("status") == "success" and bool(item.get("evidence"))
            for item in rows
        )
        condition_summary[condition] = {
            "result_file_exists": True,
            "rows": len(rows),
            "status_counts": {
                status: sum(item.get("status") == status for item in rows)
                for status in ("success", "error", "not_applicable")
            },
            "successful_rows_with_nonempty_evidence": evidence_predictions,
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(results_path),
        "dataset": str(SAMPLE_PATH),
        "evaluation_labels_source": str(EVALUATION_PATH),
        "provider": "ollama",
        "model": "qwen2.5:3b",
        "condition": "A",
        "sample_size": 300,
        "claim_ids_match_sample_in_order": True,
        "metrics": metrics,
        "other_condition_integrity": condition_summary,
        "source_sha256": {
            "condition_a_results": _sha256(results_path),
            "sample": _sha256(SAMPLE_PATH),
            "evaluation": _sha256(EVALUATION_PATH),
        },
        "graphs": [
            "condition_a_overview.svg",
            "condition_a_per_class_metrics.svg",
            "condition_a_confusion_matrix.svg",
        ],
    }
    (OUTPUT_DIR / "condition_a_metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (OUTPUT_DIR / "condition_a_metrics.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["condition", "model", "sample_size", "accuracy", "macro_precision", "macro_recall", "macro_f1"])
        writer.writerow(["A", "qwen2.5:3b", 300, metrics["accuracy"], metrics["macro_precision"], metrics["macro_recall"], metrics["macro_f1"]])
    with (OUTPUT_DIR / "condition_a_per_class.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["class", "precision", "recall", "f1", "gold_count", "predicted_count"])
        for class_name in CLASSES:
            writer.writerow([
                class_name,
                metrics["per_class"][class_name]["precision"],
                metrics["per_class"][class_name]["recall"],
                metrics["per_class"][class_name]["f1"],
                sum(gold_labels[gold_by_id[item["claim_id"]]] == class_name for item in results),
                metrics["predicted_class_counts"][class_name],
            ])
    with (OUTPUT_DIR / "condition_a_confusion_matrix.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["gold_label"] + list(CLASSES))
        for actual in CLASSES:
            writer.writerow([actual] + [metrics["confusion_matrix"][actual][predicted] for predicted in CLASSES])
    return payload


if __name__ == "__main__":
    generated = generate()
    print(json.dumps({
        "output_directory": str(OUTPUT_DIR),
        "sample_size": generated["sample_size"],
        "metrics": generated["metrics"],
        "graphs": generated["graphs"],
        "source_sha256": generated["source_sha256"],
    }, indent=2))
