"""Run only the first three claims of the fixed Condition A pilot."""

import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from app import _get_llm_provider_config
from research.config import DATASET_NAME
from research.experiment_setup import get_pilot_evaluation_records, get_pilot_llm_inputs
from research.run_condition_a import _build_prompt, _request_gemini

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CONDITION = "A_INTERNAL_KNOWLEDGE"


def _new_stem():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"condition_a_smoke_3_{timestamp}"
    suffix = 1
    while (RESULTS_DIR / f"{stem}.json").exists():
        stem = f"condition_a_smoke_3_{timestamp}_{suffix}"
        suffix += 1
    return stem


def run_smoke_test():
    evaluation_records = get_pilot_evaluation_records()
    llm_inputs = get_pilot_llm_inputs()
    selected_evaluations = evaluation_records[:3]
    selected_inputs = llm_inputs[:3]
    fixed_ids = [record["claim_id"] for record in evaluation_records]
    if [record["claim_id"] for record in selected_inputs] != fixed_ids[:3]:
        raise RuntimeError("Smoke test claims do not match the first three fixed pilot IDs.")
    if any(set(record) != {"claim_id", "claim_text", "claim_date"} for record in selected_inputs):
        raise RuntimeError("Smoke test input failed the leakage check.")
    if any(record["claim_date"] is None for record in selected_inputs):
        raise RuntimeError("Smoke test contains an invalid claim date.")

    provider = _get_llm_provider_config()
    results = []
    for evaluation, llm_input in zip(selected_evaluations, selected_inputs):
        result = {
            "claim_id": llm_input["claim_id"],
            "claim_text": llm_input["claim_text"],
            "claim_date": llm_input["claim_date"],
            "gold_label": evaluation["gold_label"],
            "predicted_label": None,
            "confidence": None,
            "explanation": None,
            "status": "error",
            "error": None,
        }
        try:
            prediction = _request_gemini(provider, _build_prompt(llm_input))
            result.update(prediction, status="success")
        except Exception as exc:
            result["error"] = str(exc)
        results.append(result)

    errors = [result for result in results if result["status"] == "error"]
    successful = [result for result in results if result["status"] == "success"]
    timestamp = datetime.now(timezone.utc).isoformat()
    stem = _new_stem()
    diagnostic = next((result["error"] for result in errors if result["error"]), None)
    payload = {
        "experiment_name": "evidence_grounded_vs_internal_knowledge",
        "condition": CONDITION,
        "model": provider["model"],
        "timestamp": timestamp,
        "dataset": DATASET_NAME,
        "number_of_claims": 3,
        "claim_ids": [result["claim_id"] for result in results],
        "successful_predictions": len(successful),
        "errors": len(errors),
        "sanitized_429_diagnostic": diagnostic if diagnostic and "429" in diagnostic else None,
        "leakage_check": "passed",
        "results": results,
    }
    json_path = RESULTS_DIR / f"{stem}.json"
    csv_path = RESULTS_DIR / f"{stem}.csv"
    metadata_path = RESULTS_DIR / f"{stem}_metadata.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=["claim_id", "claim_text", "claim_date", "gold_label", "predicted_label", "confidence", "status", "explanation", "error"])
        writer.writeheader()
        writer.writerows(results)
    metadata = {key: value for key, value in payload.items() if key != "results"}
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload, {"json": json_path, "csv": csv_path, "metadata": metadata_path}


if __name__ == "__main__":
    payload, paths = run_smoke_test()
    print(json.dumps({
        "successful_predictions": payload["successful_predictions"],
        "errors": payload["errors"],
        "sanitized_429_diagnostic": payload["sanitized_429_diagnostic"],
        "paths": {key: str(value) for key, value in paths.items()},
    }, indent=2))
