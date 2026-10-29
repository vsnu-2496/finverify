"""Metrics helpers shared by deterministic demonstration runners."""

import csv
import json
from pathlib import Path

from research.config import CLASSES


def class_metrics(gold, predicted, class_name):
    tp = sum(actual == class_name and guess == class_name for actual, guess in zip(gold, predicted))
    fp = sum(actual != class_name and guess == class_name for actual, guess in zip(gold, predicted))
    fn = sum(actual == class_name and guess != class_name for actual, guess in zip(gold, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def calculate_metrics(results):
    gold = [item["gold_label"] for item in results]
    predicted = [item["predicted_label"] for item in results]
    per_class = {name: class_metrics(gold, predicted, name) for name in CLASSES}
    confusion = {actual: {guess: 0 for guess in CLASSES} for actual in CLASSES}
    for actual, guess in zip(gold, predicted):
        confusion[actual][guess] += 1
    accuracy = sum(actual == guess for actual, guess in zip(gold, predicted)) / len(results) if results else 0.0
    return {
        "evaluated_claims": len(results),
        "accuracy": round(accuracy, 4),
        "macro_precision": round(sum(item["precision"] for item in per_class.values()) / len(CLASSES), 4),
        "macro_recall": round(sum(item["recall"] for item in per_class.values()) / len(CLASSES), 4),
        "macro_f1": round(sum(item["f1"] for item in per_class.values()) / len(CLASSES), 4),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "predicted_class_counts": {name: predicted.count(name) for name in CLASSES},
    }


def write_artifacts(directory, stem, payload, rows, matrix):
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{stem}.json"
    csv_path = directory / f"{stem}.csv"
    metadata_path = directory / f"{stem}_metadata.json"
    matrix_path = directory / f"{stem}_confusion_matrix.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["claim_id", "claim_text", "claim_date", "gold_label", "predicted_label", "confidence", "status", "prediction_mode", "model", "explanation", "variant", "evidence"]
    with csv_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    metadata = {key: value for key, value in payload.items() if key not in {"results", "variants"}}
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    with matrix_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["gold_label"] + list(CLASSES))
        for actual in CLASSES:
            writer.writerow([actual] + [matrix[actual][guess] for guess in CLASSES])
    return {"json": json_path, "csv": csv_path, "metadata": metadata_path, "confusion_matrix": matrix_path}
