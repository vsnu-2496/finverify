"""Generate deterministic synthetic-evidence Condition B demonstrations."""

from datetime import datetime, timezone
from pathlib import Path

from research.config import CLASSES, DATASET_NAME, EXPERIMENT_NAME, RANDOM_SEED
from research.demo_evidence import VARIANTS, get_demo_evidence
from research.demo_metrics import calculate_metrics, write_artifacts
from research.demo_verifier import verify_claim
from research.experiment_setup import get_pilot_evaluation_records, get_pilot_llm_inputs

FINAL_DIR = Path(__file__).resolve().parent / "results" / "final_demo"
RUN_NOTE = "These demonstration results use synthetic local evidence and a deterministic fallback verifier. They are not real SEC, Alpha Vantage, or Gemini results and must not be interpreted as measured LLM performance."


def run_condition_b_demo():
    evaluations = get_pilot_evaluation_records()
    inputs = get_pilot_llm_inputs()
    if len(evaluations) != 75 or len(inputs) != 75:
        raise RuntimeError("The fixed pilot must contain exactly 75 records.")
    all_variants = {}
    flat_rows = []
    for variant in VARIANTS:
        rows = []
        for evaluation, safe_input in zip(evaluations, inputs):
            evidence = get_demo_evidence(safe_input["claim_id"], safe_input["claim_text"], safe_input["claim_date"], variant)
            prediction = verify_claim(**safe_input, evidence=evidence)
            rows.append({
                **safe_input,
                "gold_label": evaluation["gold_label"],
                **prediction,
                "status": "success",
                "variant": variant,
                "evidence": evidence,
            })
        metrics = calculate_metrics(rows)
        all_variants[variant] = {"metrics": metrics, "results": rows}
        flat_rows.extend(rows)

    timestamp = datetime.now(timezone.utc).isoformat()
    combined_metrics = all_variants["B3_COMBINED"]["metrics"]
    payload = {
        "experiment_name": EXPERIMENT_NAME,
        "condition": "B_EVIDENCE_GROUNDED",
        "run_mode": "DEMO_FALLBACK",
        "prediction_mode": "DEMO_FALLBACK",
        "model": "deterministic-demo-verifier",
        "timestamp": timestamp,
        "dataset": DATASET_NAME,
        "random_seed": RANDOM_SEED,
        "number_of_claims": 75,
        "claim_ids": [item["claim_id"] for item in inputs],
        "demonstration_note": RUN_NOTE,
        "variants": all_variants,
        "metrics": combined_metrics,
        "results": all_variants["B3_COMBINED"]["results"],
    }
    paths = write_artifacts(FINAL_DIR, "condition_b_demo_75", payload, flat_rows, combined_metrics["confusion_matrix"])
    return payload, paths


if __name__ == "__main__":
    payload, paths = run_condition_b_demo()
    print({"variants": {key: value["metrics"] for key, value in payload["variants"].items()}, "paths": {key: str(value) for key, value in paths.items()}})
