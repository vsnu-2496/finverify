"""Generate a deterministic Condition A fallback demonstration."""

from datetime import datetime, timezone
from pathlib import Path

from research.config import CLASSES, DATASET_NAME, EXPERIMENT_NAME, RANDOM_SEED
from research.demo_metrics import calculate_metrics, write_artifacts
from research.demo_verifier import verify_claim
from research.experiment_setup import get_pilot_evaluation_records, get_pilot_llm_inputs

FINAL_DIR = Path(__file__).resolve().parent / "results" / "final_demo"
RUN_NOTE = "These demonstration results are produced by a deterministic fallback verifier because the Gemini API free-tier quota was exhausted. They are intended to validate the experimental software pipeline and visualization, not to represent measured LLM performance."


def run_condition_a_demo():
    evaluations = get_pilot_evaluation_records()
    inputs = get_pilot_llm_inputs()
    if len(evaluations) != 75 or len(inputs) != 75:
        raise RuntimeError("The fixed pilot must contain exactly 75 records.")
    if [item["claim_id"] for item in evaluations] != [item["claim_id"] for item in inputs]:
        raise RuntimeError("Evaluation and safe input IDs differ.")
    gold_counts = {label: sum(item["gold_label"] == label for item in evaluations) for label in CLASSES}
    if gold_counts != {"SUPPORTED": 25, "REFUTED": 25, "UNVERIFIABLE": 25}:
        raise RuntimeError(f"Unexpected fixed pilot distribution: {gold_counts}")

    rows = []
    for evaluation, safe_input in zip(evaluations, inputs):
        prediction = verify_claim(**safe_input)
        rows.append({
            **safe_input,
            "gold_label": evaluation["gold_label"],
            **prediction,
            "status": "success",
            "variant": "A_INTERNAL_KNOWLEDGE",
            "evidence": [],
        })
    metrics = calculate_metrics(rows)
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_name": EXPERIMENT_NAME,
        "condition": "A_INTERNAL_KNOWLEDGE",
        "run_mode": "DEMO_FALLBACK",
        "prediction_mode": "DEMO_FALLBACK",
        "model": "deterministic-demo-verifier",
        "timestamp": timestamp,
        "dataset": DATASET_NAME,
        "random_seed": RANDOM_SEED,
        "number_of_claims": 75,
        "claim_ids": [item["claim_id"] for item in rows],
        "gold_class_counts": gold_counts,
        "demonstration_note": RUN_NOTE,
        "metrics": metrics,
        "results": rows,
    }
    paths = write_artifacts(FINAL_DIR, "condition_a_demo_75", payload, rows, metrics["confusion_matrix"])
    return payload, paths


if __name__ == "__main__":
    payload, paths = run_condition_a_demo()
    print({"metrics": payload["metrics"], "paths": {key: str(value) for key, value in paths.items()}})
