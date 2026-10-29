"""Run resumable 300-claim SEC, Alpha Vantage, and combined experiments."""

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import time

import requests

from app import (
    _classify_financial_claim,
    _get_llm_provider_config,
    _normalize_evidence_items,
    _parse_llm_json_response,
    _retrieve_alpha_vantage_evidence,
    _retrieve_sec_evidence,
)
from data.finfact_loader import validate_no_llm_leakage
from research.config import CLASSES, LABEL_MAPPING

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SAMPLE_PATH = DATA_DIR / "finfact_research_sample.json"
EVALUATION_PATH = DATA_DIR / "finfact_research_evaluation.json"
MAX_ATTEMPTS = 4
MAX_REQUESTS_PER_RUN = 20
REQUEST_TIMEOUT_SECONDS = (10, 30)
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
QUOTA_ERROR_MARKERS = ("generate_content_free_tier_requests", "quota exceeded", "limit: 20")

CONDITIONS = {
    "B1_SEC": {"sources": ("SEC",), "result": DATA_DIR / "condition_b1_sec_results.json", "progress": DATA_DIR / "condition_b1_sec_progress.json"},
    "B2_ALPHA_VANTAGE": {"sources": ("Alpha Vantage",), "result": DATA_DIR / "condition_b2_alpha_vantage_results.json", "progress": DATA_DIR / "condition_b2_alpha_vantage_progress.json"},
    "B3_COMBINED": {"sources": ("SEC", "Alpha Vantage"), "result": DATA_DIR / "condition_b3_combined_results.json", "progress": DATA_DIR / "condition_b3_combined_progress.json"},
}


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


def _is_quota_error(message):
    lowered = message.lower()
    return any(marker in lowered for marker in QUOTA_ERROR_MARKERS)


def _retry_delay(response, attempt):
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            return min(float(retry_after), 60.0)
        except ValueError:
            pass
    return min(2 ** (attempt - 1), 60.0)


def _claim_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def _build_evidence(record, sources):
    validate_no_llm_leakage(record)
    classification = _classify_financial_claim(record["claim_text"])
    entity = classification["entity"]
    claim_type = classification["claim_type"]
    cutoff = _claim_date(record["claim_date"])
    evidence = []
    source_errors = []
    if "SEC" in sources:
        found, errors = _retrieve_sec_evidence(record["claim_text"], claim_type, entity, cutoff)
        evidence.extend(found)
        source_errors.extend(errors)
    if "Alpha Vantage" in sources:
        found, errors = _retrieve_alpha_vantage_evidence(record["claim_text"], claim_type, entity, cutoff)
        evidence.extend(found)
        source_errors.extend(errors)
    return _normalize_evidence_items(evidence, cutoff), source_errors, classification


def _build_prompt(record, evidence):
    if set(record) != {"claim_id", "claim_text", "claim_date"}:
        raise RuntimeError(f"Unexpected research record fields: {sorted(record)}")
    validate_no_llm_leakage(record)
    evidence_payload = json.dumps(evidence, ensure_ascii=False)
    system_prompt = (
        "You are a financial claim verifier. Use ONLY the supplied evidence below. "
        "Do not use web search, internal knowledge, Fin-Fact evidence, Fin-Fact labels, "
        "or any source other than the supplied evidence. Classify the claim into exactly "
        "one verdict: SUPPORTED, REFUTED, or UNVERIFIABLE. Return UNVERIFIABLE when the "
        "supplied evidence is insufficient or temporally unknown. Return strict JSON with "
        "keys verdict, confidence, explanation. Confidence is diagnostic only and must be "
        "a number from 0.0 to 1.0."
    )
    return (
        f"{system_prompt}\n\nClaim ID: {record['claim_id']}\n"
        f"Claim date: {record['claim_date']}\nClaim: {record['claim_text']}\n\n"
        f"Supplied evidence: {evidence_payload}"
    )


class QuotaExhaustedError(RuntimeError):
    pass


class RequestLimitReachedError(RuntimeError):
    pass


def _request_gemini(provider, prompt, run_state):
    if provider.get("model") != "gemini-3.6-flash":
        raise RuntimeError(f"Expected Gemini model gemini-3.6-flash, got {provider.get('model')!r}")
    url = f"{provider['base_url']}/{provider['model']}:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if run_state["requests_this_run"] >= MAX_REQUESTS_PER_RUN:
            raise RequestLimitReachedError("Free-tier batch limit reached. Resume later.")
        try:
            run_state["requests_this_run"] += 1
            response = requests.post(url, params={"key": provider["api_key"]}, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code == 429 and _is_quota_error(_response_error(response)):
                raise QuotaExhaustedError(_response_error(response))
            if response.status_code in TRANSIENT_STATUS_CODES and attempt < MAX_ATTEMPTS:
                run_state["retry_count"] += 1
                time.sleep(_retry_delay(response, attempt))
                continue
            response.raise_for_status()
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
            return {"verdict": verdict, "confidence": round(confidence, 3), "explanation": explanation.strip()}
        except requests.RequestException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code == 429 and exc.response is not None and _is_quota_error(_response_error(exc.response)):
                raise QuotaExhaustedError(_response_error(exc.response)) from exc
            if status_code in TRANSIENT_STATUS_CODES and attempt < MAX_ATTEMPTS:
                run_state["retry_count"] += 1
                time.sleep(_retry_delay(exc.response, attempt))
                continue
            raise RuntimeError(_safe_error(exc)) from exc
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(_safe_error(f"Malformed Gemini response: {exc}")) from exc
    raise RuntimeError("Gemini request failed after maximum retries")


def _metrics(results, gold_by_id):
    successful = [item for item in results if item["status"] == "success"]
    gold = [LABEL_MAPPING[gold_by_id[item["claim_id"]]] for item in successful]
    predicted = [item["verdict"] for item in successful]
    confusion = {actual: {guess: 0 for guess in CLASSES} for actual in CLASSES}
    for actual, guess in zip(gold, predicted):
        confusion[actual][guess] += 1
    return {"evaluated_claims": len(successful), "confusion_matrix": confusion, "predicted_class_counts": {label: predicted.count(label) for label in CLASSES}}


def _save(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_condition(condition_name):
    config = CONDITIONS[condition_name]
    sample = _load_json(SAMPLE_PATH)
    evaluation = _load_json(EVALUATION_PATH)
    if len(sample) != 300 or len(evaluation) != 300:
        raise RuntimeError("Fixed research sample and evaluation must each contain exactly 300 records")
    sample_ids = [record["claim_id"] for record in sample]
    if len(set(sample_ids)) != 300 or sample_ids != [record["claim_id"] for record in evaluation]:
        raise RuntimeError("Fixed research sample and evaluation claim IDs are not aligned")
    if any(record.get("claim_date") is None for record in sample):
        raise RuntimeError("All 300 canonical Fin-Fact claim dates must be valid")
    gold_by_id = {record["claim_id"]: record["gold_label"] for record in evaluation}
    provider = _get_llm_provider_config()
    if not provider or provider.get("type") != "gemini":
        raise RuntimeError("Configured Gemini provider is unavailable")

    existing = _load_json(config["result"]) if config["result"].exists() else []
    existing_by_id = {item["claim_id"]: item for item in existing if item["claim_id"] in set(sample_ids)}
    results = []
    for record in sample:
        results.append(existing_by_id.get(record["claim_id"], {
            "claim_id": record["claim_id"], "claim_text": record["claim_text"], "claim_date": record["claim_date"],
            "verdict": None, "confidence": None, "explanation": None, "status": "error", "error": None,
            "evidence": [], "source_errors": [], "claim_type": None, "entity": None,
        }))

    run_state = {"requests_this_run": 0, "retry_count": 0}
    quota_exhausted = False
    for index, record in enumerate(sample):
        result = results[index]
        if result["status"] == "success":
            continue
        try:
            evidence, source_errors, classification = _build_evidence(record, config["sources"])
            result.update(evidence=evidence, source_errors=source_errors, claim_type=classification["claim_type"], entity=classification["entity"]["name"] if classification["entity"] else None)
            hard_errors = [item for item in source_errors if item.get("status") == "error"]
            if hard_errors:
                raise RuntimeError("Evidence retrieval failed: " + json.dumps(hard_errors, ensure_ascii=False))
            prediction = _request_gemini(provider, _build_prompt({key: record[key] for key in ("claim_id", "claim_text", "claim_date")}, evidence), run_state)
            result.update(prediction, status="success", error=None)
        except QuotaExhaustedError as exc:
            result.update(verdict=None, confidence=None, explanation=None, status="error", error=str(exc))
            quota_exhausted = True
            _save(config["result"], results)
            break
        except RequestLimitReachedError:
            _save(config["result"], results)
            break
        except Exception as exc:
            result.update(verdict=None, confidence=None, explanation=None, status="error", error=_safe_error(exc))
        _save(config["result"], results)

    successful = sum(item["status"] == "success" for item in results)
    progress = {
        "condition": condition_name, "sources": list(config["sources"]), "total_claims": 300,
        "successful": successful, "failed": sum(1 for item in results if item["status"] == "error" and item["error"]),
        "remaining": 300 - successful, "requests_this_run": run_state["requests_this_run"],
        "retry_count": run_state["retry_count"], "status": "complete" if successful == 300 else "quota_exhausted" if quota_exhausted else "batch_complete",
        "model": provider["model"], "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_errors": sorted({item["error"] for item in results if item["error"]}), "metrics": _metrics(results, gold_by_id),
    }
    _save(config["result"], results)
    _save(config["progress"], progress)
    return progress


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("condition", choices=CONDITIONS)
    args = parser.parse_args()
    print(json.dumps(run_condition(args.condition), ensure_ascii=False, indent=2))