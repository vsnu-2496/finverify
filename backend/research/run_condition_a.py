"""Execute Condition A against the fixed Fin-Fact pilot only."""

import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import requests

from app import _get_llm_provider_config, _parse_llm_json_response
from research.config import CLASSES, DATASET_NAME, EXPERIMENT_NAME, RANDOM_SEED
from research.experiment_setup import get_pilot_evaluation_records, get_pilot_llm_inputs

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CONDITION = "A_INTERNAL_KNOWLEDGE"
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = (5, 15)
MAX_WORKERS = 1
MAX_RETRY_AFTER_SECONDS = 60
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
FORBIDDEN_INPUT_KEYS = {
    "gold_label", "label", "evidence", "justification", "sci_digest", "issues",
    "hrefs", "url", "image_data", "visualization_bias",
}

SYSTEM_PROMPT = (
    "You are verifying a financial claim using only your internal knowledge. "
    "No external evidence or web search is available. "
    "Classify the claim as exactly one of: SUPPORTED, REFUTED, UNVERIFIABLE.\n\n"
    "SUPPORTED: Your knowledge supports the claim.\n"
    "REFUTED: Your knowledge indicates the claim is false or contradicted.\n"
    "UNVERIFIABLE: Your knowledge is insufficient to reliably determine whether the claim is true or false.\n\n"
    "Do not invent facts or sources.\n\n"
    "Return strict JSON:\n"
    '{"verdict": "SUPPORTED | REFUTED | UNVERIFIABLE", "confidence": 0.0, '
    '"explanation": "brief explanation"}\n\n'
    "Confidence must be a number between 0 and 1. "
    "This value is the model's self-reported confidence for the predicted verdict, "
    "not a calibrated probability or statistical confidence interval."
)


def _assert_safe_llm_input(record):
    keys = set(record)
    if keys != {"claim_id", "claim_text", "claim_date"}:
        raise RuntimeError(f"Unsafe LLM input keys detected: {sorted(keys)}")
    if keys & FORBIDDEN_INPUT_KEYS:
        raise RuntimeError(f"Forbidden LLM input keys detected: {sorted(keys & FORBIDDEN_INPUT_KEYS)}")


def _build_prompt(record):
    _assert_safe_llm_input(record)
    return (
        f"Claim ID: {record['claim_id']}\n"
        f"Claim date: {record['claim_date']}\n"
        f"Claim: {record['claim_text']}"
    )


def _safe_error(error):
    return re.sub(r"([?&]key=)[^&\s]+", r"\1[REDACTED]", str(error))


def _response_error(response):
    try:
        error = response.json().get("error", {})
        message = error.get("message") or response.reason
        return _safe_error(f"HTTP {response.status_code}: {message}")
    except (ValueError, TypeError):
        return _safe_error(f"HTTP {response.status_code}: {response.reason}")


def _retry_delay(response, attempt):
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            pass
    try:
        body = response.json()
        message = body.get("error", {}).get("message", "")
        match = re.search(r"Please retry in ([0-9.]+)s", message)
        if match:
            return min(float(match.group(1)), MAX_RETRY_AFTER_SECONDS)
    except (ValueError, TypeError):
        pass
    return min(2 ** (attempt - 1), MAX_RETRY_AFTER_SECONDS)


def _request_gemini(provider, prompt):
    if provider is None or provider.get("type") != "gemini":
        raise RuntimeError("Condition A requires the configured Gemini provider.")

    url = f"{provider['base_url']}/{provider['model']}:generateContent"
    payload = {"contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\n{prompt}"}]}]}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                url,
                params={"key": provider["api_key"]},
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code in TRANSIENT_STATUS_CODES and attempt < MAX_ATTEMPTS:
                time.sleep(_retry_delay(response, attempt))
                continue
            if response.status_code == 429:
                raise RuntimeError(_response_error(response))
            response.raise_for_status()
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = _parse_llm_json_response(text)
            verdict = parsed.get("verdict")
            if verdict not in CLASSES:
                raise ValueError(f"Invalid verdict: {verdict!r}")
            confidence = parsed.get("confidence")
            if isinstance(confidence, bool):
                raise ValueError("Confidence must be a number between 0 and 1.")
            confidence = float(confidence)
            if not 0 <= confidence <= 1:
                raise ValueError("Confidence must be a number between 0 and 1.")
            explanation = parsed.get("explanation")
            if not isinstance(explanation, str) or not explanation.strip():
                raise ValueError("Explanation must be a non-empty string.")
            return {
                "predicted_label": verdict,
                "confidence": round(confidence, 3),
                "explanation": explanation.strip(),
            }
        except requests.RequestException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in TRANSIENT_STATUS_CODES and attempt < MAX_ATTEMPTS:
                time.sleep(_retry_delay(exc.response, attempt))
                continue
            if status_code == 429 and exc.response is not None:
                raise RuntimeError(_response_error(exc.response)) from exc
            raise RuntimeError(_safe_error(exc)) from exc
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(_safe_error(f"Malformed Gemini response: {exc}")) from exc

    raise RuntimeError("Gemini request failed after maximum retries.")


def _new_result_stem():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"condition_a_internal_75_{timestamp}"
    suffix = 1
    while (RESULTS_DIR / f"{stem}.json").exists():
        stem = f"condition_a_internal_75_{timestamp}_{suffix}"
        suffix += 1
    return stem


def _metric_for_class(gold, predicted, class_name):
    true_positive = sum(1 for actual, guess in zip(gold, predicted) if actual == class_name and guess == class_name)
    false_positive = sum(1 for actual, guess in zip(gold, predicted) if actual != class_name and guess == class_name)
    false_negative = sum(1 for actual, guess in zip(gold, predicted) if actual == class_name and guess != class_name)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _calculate_metrics(results):
    successful = [result for result in results if result["status"] == "success"]
    gold = [result["gold_label"] for result in successful]
    predicted = [result["predicted_label"] for result in successful]
    per_class = {name: _metric_for_class(gold, predicted, name) for name in CLASSES}
    confusion_matrix = {actual: {guess: 0 for guess in CLASSES} for actual in CLASSES}
    for actual, guess in zip(gold, predicted):
        confusion_matrix[actual][guess] += 1
    accuracy = sum(actual == guess for actual, guess in zip(gold, predicted)) / len(successful) if successful else 0.0
    return {
        "evaluated_claims": len(successful),
        "accuracy": accuracy,
        "macro_precision": sum(item["precision"] for item in per_class.values()) / len(CLASSES),
        "macro_recall": sum(item["recall"] for item in per_class.values()) / len(CLASSES),
        "macro_f1": sum(item["f1"] for item in per_class.values()) / len(CLASSES),
        "per_class": per_class,
        "confusion_matrix": confusion_matrix,
        "predicted_class_counts": {name: predicted.count(name) for name in CLASSES},
    }


def run_condition_a():
    evaluation_records = get_pilot_evaluation_records()
    llm_inputs = get_pilot_llm_inputs()
    if len(evaluation_records) != 75 or len(llm_inputs) != 75:
        raise RuntimeError("Fixed pilot must contain exactly 75 records.")
    if [record["claim_id"] for record in evaluation_records] != [record["claim_id"] for record in llm_inputs]:
        raise RuntimeError("Evaluation and LLM input claim IDs do not match.")
    if any(record["claim_date"] is None for record in llm_inputs):
        raise RuntimeError("All fixed pilot claim dates must be valid ISO dates.")

    gold_by_id = {record["claim_id"]: record["gold_label"] for record in evaluation_records}
    provider = _get_llm_provider_config()
    if provider is None or provider.get("type") != "gemini":
        raise RuntimeError("No configured Gemini provider is available.")

    def process_record(record):
        result = {
            "claim_id": record["claim_id"],
            "claim_text": record["claim_text"],
            "claim_date": record["claim_date"],
            "gold_label": gold_by_id[record["claim_id"]],
            "predicted_label": None,
            "confidence": None,
            "explanation": None,
            "status": "error",
            "error": None,
        }
        try:
            prediction = _request_gemini(provider, _build_prompt(record))
            result.update(prediction, status="success")
        except Exception as exc:  # Each failed claim remains visible in outputs.
            result["error"] = str(exc)

        return result

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(process_record, llm_inputs))

    metrics = _calculate_metrics(results)
    error_count = sum(result["status"] == "error" for result in results)
    timestamp = datetime.now(timezone.utc).isoformat()
    stem = _new_result_stem()
    result_payload = {
        "experiment_name": EXPERIMENT_NAME,
        "condition": CONDITION,
        "model": provider["model"],
        "timestamp": timestamp,
        "random_seed": RANDOM_SEED,
        "dataset": DATASET_NAME,
        "number_of_claims": len(results),
        "claim_ids": [result["claim_id"] for result in results],
        "results": results,
        "errors": [result for result in results if result["status"] == "error"],
        "metrics": {**metrics, "total_claims": len(results), "errors": error_count, "error_rate": error_count / len(results)},
    }
    json_path = RESULTS_DIR / f"{stem}.json"
    csv_path = RESULTS_DIR / f"{stem}.csv"
    metadata_path = RESULTS_DIR / f"{stem}_metadata.json"
    matrix_path = RESULTS_DIR / f"{stem}_confusion_matrix.csv"
    json_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=["claim_id", "claim_text", "claim_date", "gold_label", "predicted_label", "confidence", "status", "explanation", "error"])
        writer.writeheader()
        writer.writerows(results)
    metadata_path.write_text(json.dumps({key: value for key, value in result_payload.items() if key not in {"results", "errors"}}, ensure_ascii=False, indent=2), encoding="utf-8")
    with matrix_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["gold_label"] + list(CLASSES))
        for actual in CLASSES:
            writer.writerow([actual] + [metrics["confusion_matrix"][actual][guess] for guess in CLASSES])
    return result_payload, {"json": json_path, "csv": csv_path, "metadata": metadata_path, "confusion_matrix": matrix_path}


if __name__ == "__main__":
    payload, paths = run_condition_a()
    print(json.dumps({"metrics": payload["metrics"], "paths": {key: str(value) for key, value in paths.items()}}, indent=2))
