"""Run the fixed 300-claim Fin-Fact Condition A experiment."""

from collections import Counter
import json
from pathlib import Path
import re
import time

import requests

from app import _get_llm_provider_config, _parse_llm_json_response
from data.finfact_loader import validate_no_llm_leakage
from research.config import CLASSES, LABEL_MAPPING


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SAMPLE_PATH = DATA_DIR / "finfact_research_sample.json"
EVALUATION_PATH = DATA_DIR / "finfact_research_evaluation.json"
RESULTS_PATH = DATA_DIR / "condition_a_results.json"
PROGRESS_PATH = DATA_DIR / "condition_a_progress.json"
REPORT_PATH = DATA_DIR / "condition_a_evaluation.json"
EXAMPLES_PATH = DATA_DIR / "condition_a_examples.json"
MAX_ATTEMPTS = 4
MAX_REQUESTS_PER_RUN = 20
REQUEST_TIMEOUT_SECONDS = (10, 30)
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
QUOTA_ERROR_MARKERS = (
    "generate_content_free_tier_requests",
    "Quota exceeded",
    "limit: 20",
)

SYSTEM_PROMPT = (
    "You are verifying a financial claim using only your internal knowledge.\n\n"
    "Classify the claim into exactly one of:\n"
    "SUPPORTED\n"
    "REFUTED\n"
    "UNVERIFIABLE\n\n"
    "SUPPORTED = the claim is consistent with your knowledge.\n"
    "REFUTED = the claim contradicts reliable knowledge.\n"
    "UNVERIFIABLE = there is insufficient information to determine whether it is true or false.\n\n"
    "Do not use external search, browsing, retrieval, SEC data, Alpha Vantage, or Fin-Fact evidence.\n\n"
    "Return JSON only:\n"
    '{"verdict": "SUPPORTED | REFUTED | UNVERIFIABLE", "confidence": 0.0, '
    '"explanation": "brief explanation"}'
)


def _load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _safe_error(error):
    return re.sub(r"([?&]key=)[^&\s]+", r"\1[REDACTED]", str(error))


def _response_error(response):
    try:
        message = response.json().get("error", {}).get("message") or response.reason
    except (ValueError, TypeError):
        message = response.reason
    return _safe_error(f"HTTP {response.status_code}: {message}")


def _retry_delay(response, attempt):
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            return min(float(retry_after), 60.0)
        except ValueError:
            pass
    return min(2 ** (attempt - 1), 60.0)


def _build_prompt(record):
    if set(record) != {"claim_id", "claim_text", "claim_date"}:
        raise RuntimeError(f"Unexpected research record fields: {sorted(record)}")
    validate_no_llm_leakage(record)

    date_line = f"Claim date: {record['claim_date']}\n\n" if record.get("claim_date") else ""
    prompt = (
        f"{date_line}"
        f"Claim:\n{record['claim_text']}\n\n"
        "Classify the claim into exactly one of:\n"
        "SUPPORTED\nREFUTED\nUNVERIFIABLE\n\n"
        "SUPPORTED = the claim is consistent with your knowledge.\n"
        "REFUTED = the claim contradicts reliable knowledge.\n"
        "UNVERIFIABLE = there is insufficient information to determine whether it is true or false.\n\n"
        "Do not use external search, browsing, retrieval, SEC data, Alpha Vantage, or Fin-Fact evidence.\n\n"
        "Return JSON only:\n"
        '{"verdict": "SUPPORTED | REFUTED | UNVERIFIABLE", "confidence": 0.0, '
        '"explanation": "brief explanation"}'
    )
    return f"{SYSTEM_PROMPT}\n\n{prompt}"


class QuotaExhaustedError(RuntimeError):
    pass


class RequestLimitReachedError(RuntimeError):
    pass


def _is_quota_error(message):
    return all(marker.lower() in message.lower() for marker in QUOTA_ERROR_MARKERS[:2]) or QUOTA_ERROR_MARKERS[2].lower() in message.lower()


def _request_gemini(provider, prompt, run_state):
    url = f"{provider['base_url']}/{provider['model']}:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if run_state["requests_this_run"] >= MAX_REQUESTS_PER_RUN:
            raise RequestLimitReachedError("Free-tier batch limit reached. Resume later.")
        try:
            run_state["requests_this_run"] += 1
            response = requests.post(
                url,
                params={"key": provider["api_key"]},
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code == 429 and _is_quota_error(_response_error(response)):
                raise QuotaExhaustedError(_response_error(response))
            if response.status_code in TRANSIENT_STATUS_CODES and attempt < MAX_ATTEMPTS:
                run_state["retry_count"] += 1
                time.sleep(_retry_delay(response, attempt))
                continue
            if response.status_code >= 400:
                raise RuntimeError(_response_error(response))
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = _parse_llm_json_response(text)
            verdict = str(parsed.get("verdict", "")).strip().upper()
            if verdict not in CLASSES:
                raise ValueError(f"Invalid verdict: {verdict!r}")
            confidence = parsed.get("confidence")
            if isinstance(confidence, bool):
                raise ValueError("Confidence must be numeric")
            confidence = float(confidence)
            if not 0 <= confidence <= 1:
                raise ValueError("Confidence must be between 0 and 1")
            explanation = parsed.get("explanation")
            if not isinstance(explanation, str) or not explanation.strip():
                raise ValueError("Explanation must be non-empty")
            return {
                "verdict": verdict,
                "confidence": round(confidence, 3),
                "explanation": explanation.strip(),
            }
        except requests.RequestException as exc:
            status_code = getattr(exc.response, "status_code", None)
            error = _safe_error(exc)
            if status_code == 429 and exc.response is not None and _is_quota_error(_response_error(exc.response)):
                raise QuotaExhaustedError(_response_error(exc.response)) from exc
            if status_code in TRANSIENT_STATUS_CODES and attempt < MAX_ATTEMPTS:
                run_state["retry_count"] += 1
                time.sleep(_retry_delay(exc.response, attempt))
                continue
            raise RuntimeError(error) from exc
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(_safe_error(f"Malformed Gemini response: {exc}")) from exc
    raise RuntimeError("Gemini request failed after maximum retries")


def _calculate_metrics(results, gold_by_id):
    successful = [result for result in results if result["status"] == "success"]
    gold = [LABEL_MAPPING[gold_by_id[result["claim_id"]]] for result in successful]
    predicted = [result["verdict"] for result in successful]
    per_class = {}
    for class_name in CLASSES:
        tp = sum(actual == class_name and guess == class_name for actual, guess in zip(gold, predicted))
        fp = sum(actual != class_name and guess == class_name for actual, guess in zip(gold, predicted))
        fn = sum(actual == class_name and guess != class_name for actual, guess in zip(gold, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[class_name] = {"precision": precision, "recall": recall, "f1": f1}

    confusion = {actual: {guess: 0 for guess in CLASSES} for actual in CLASSES}
    for actual, guess in zip(gold, predicted):
        confusion[actual][guess] += 1
    return {
        "accuracy": sum(actual == guess for actual, guess in zip(gold, predicted)) / len(successful) if successful else 0.0,
        "macro_precision": sum(item["precision"] for item in per_class.values()) / len(CLASSES),
        "macro_recall": sum(item["recall"] for item in per_class.values()) / len(CLASSES),
        "macro_f1": sum(item["f1"] for item in per_class.values()) / len(CLASSES),
        "per_class_metrics": per_class,
        "confusion_matrix": confusion,
    }


def run_condition_a_300():
    sample = _load_json(SAMPLE_PATH)
    evaluation = _load_json(EVALUATION_PATH)
    if len(sample) != 300 or len(evaluation) != 300:
        raise RuntimeError("Fixed research sample and evaluation must each contain exactly 300 records")
    sample_ids = [record["claim_id"] for record in sample]
    if len(set(sample_ids)) != 300:
        raise RuntimeError("Fixed research sample must contain exactly 300 unique claim IDs")
    if sample_ids != [record["claim_id"] for record in evaluation]:
        raise RuntimeError("Sample and evaluation claim IDs are not aligned")

    gold_by_id = {record["claim_id"]: record["gold_label"] for record in evaluation}
    if set(gold_by_id.values()) != set(LABEL_MAPPING):
        raise RuntimeError("Unexpected evaluation labels")
    provider = _get_llm_provider_config()
    if not provider or provider.get("type") != "gemini":
        raise RuntimeError("Configured Gemini provider is unavailable")

    existing = _load_json(RESULTS_PATH) if RESULTS_PATH.exists() else []
    existing_by_id = {item["claim_id"]: item for item in existing if item["claim_id"] in set(sample_ids)}
    results = []
    for record in sample:
        result = existing_by_id.get(record["claim_id"], {
            "claim_id": record["claim_id"],
            "claim_text": record["claim_text"],
            "claim_date": record.get("claim_date"),
            "verdict": None,
            "confidence": None,
            "explanation": None,
            "status": "error",
            "error": None,
        })
        results.append(result)

    run_state = {"requests_this_run": 0, "retry_count": 0}
    quota_exhausted = False
    for index, record in enumerate(sample):
        result = results[index]
        if result["status"] == "success":
            continue
        try:
            prediction = _request_gemini(provider, _build_prompt({
                "claim_id": record["claim_id"],
                "claim_text": record["claim_text"],
                "claim_date": record.get("claim_date"),
            }), run_state)
            result.update(prediction, status="success", error=None)
        except QuotaExhaustedError as exc:
            result.update(verdict=None, confidence=None, explanation=None, status="error", error=str(exc))
            quota_exhausted = True
            break
        except RequestLimitReachedError as exc:
            break
        except Exception as exc:
            result.update(verdict=None, confidence=None, explanation=None, status="error", error=str(exc))

        RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    successful = sum(item["status"] == "success" for item in results)
    remaining = len(results) - successful
    status = "complete" if successful == len(results) else "quota_exhausted" if quota_exhausted else "batch_complete"
    progress = {
        "total_claims": len(results),
        "successful_predictions": successful,
        "remaining_claims": remaining,
        "requests_this_run": run_state["requests_this_run"],
        "status": status,
    }
    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PROGRESS_PATH.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if run_state["requests_this_run"] >= MAX_REQUESTS_PER_RUN:
        print("Free-tier batch limit reached. Resume later.")
    if successful < len(results):
        print("Research metrics not yet interpretable because Condition A is incomplete.")
    return progress


if __name__ == "__main__":
    report = run_condition_a_300()
    print(json.dumps(report, ensure_ascii=False, indent=2))
