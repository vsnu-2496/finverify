"""Unified 300-claim experiment runner for the Fin-Fact research benchmark.

All four conditions (A, B1, B2, B3) use Ollama (local) with qwen2.5:3b.
No API key required. No rate limits. No cost.

Old Gemini and OpenAI result files are NEVER touched.

Temporal safeguards, leakage protection, and all existing architecture
from run_condition_a_300.py / run_condition_b_300.py are preserved.

Usage:
    python run_openai_experiment_300.py A
    python run_openai_experiment_300.py B1
    python run_openai_experiment_300.py B2
    python run_openai_experiment_300.py B3

Result files:
    backend/data/condition_a_ollama_qwen25_3b_results.json
    backend/data/condition_a_ollama_qwen25_3b_progress.json
    backend/data/condition_b1_ollama_qwen25_3b_results.json
    backend/data/condition_b1_ollama_qwen25_3b_progress.json
    backend/data/condition_b2_ollama_qwen25_3b_results.json
    backend/data/condition_b2_ollama_qwen25_3b_progress.json
    backend/data/condition_b3_ollama_qwen25_3b_results.json
    backend/data/condition_b3_ollama_qwen25_3b_progress.json
"""

import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── project path setup ────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from app import (
    _classify_financial_claim,
    _normalize_evidence_items,
    _parse_llm_json_response,
    _retrieve_alpha_vantage_evidence,
    _retrieve_sec_evidence,
)
from data.finfact_loader import validate_no_llm_leakage
from research.config import CLASSES, LABEL_MAPPING

# ── paths ─────────────────────────────────────────────────────────────────────
DATA_DIR = BACKEND_DIR / "data"
SAMPLE_PATH = DATA_DIR / "finfact_research_sample.json"
EVALUATION_PATH = DATA_DIR / "finfact_research_evaluation.json"

CONDITION_CONFIGS = {
    "A": {
        "result_path":   DATA_DIR / "condition_a_ollama_qwen25_3b_results.json",
        "progress_path": DATA_DIR / "condition_a_ollama_qwen25_3b_progress.json",
        "sources": (),
    },
    "B1": {
        "result_path":   DATA_DIR / "condition_b1_ollama_qwen25_3b_results.json",
        "progress_path": DATA_DIR / "condition_b1_ollama_qwen25_3b_progress.json",
        "sources": ("SEC",),
    },
    "B2": {
        "result_path":   DATA_DIR / "condition_b2_ollama_qwen25_3b_results.json",
        "progress_path": DATA_DIR / "condition_b2_ollama_qwen25_3b_progress.json",
        "sources": ("Alpha Vantage",),
    },
    "B3": {
        "result_path":   DATA_DIR / "condition_b3_ollama_qwen25_3b_results.json",
        "progress_path": DATA_DIR / "condition_b3_ollama_qwen25_3b_progress.json",
        "sources": ("SEC", "Alpha Vantage"),
    },
}

# ── tuning ────────────────────────────────────────────────────────────────────
MAX_ATTEMPTS = 4
REQUEST_TIMEOUT = (10, 300)        # generous timeout for local CPU inference
INTER_REQUEST_DELAY = 0.5          # no rate limit locally, brief pause for stability
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
OLLAMA_BASE_URL = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "qwen2.5:3b"
SEC_APPLICABLE_CLAIM_TYPES = {
    "financial/revenue",
    "percentage/growth",
    "share buyback",
    "stock/market movement",
    "corporate operations",
}

# ── prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT_A = (
    "You are verifying a financial claim using only your internal knowledge.\n\n"
    "Classify the claim into exactly one of:\n"
    "SUPPORTED\n"
    "REFUTED\n"
    "UNVERIFIABLE\n\n"
    "SUPPORTED = the claim is consistent with your knowledge.\n"
    "REFUTED = the claim contradicts reliable knowledge.\n"
    "UNVERIFIABLE = there is insufficient information to determine whether it is "
    "true or false.\n\n"
    "Do not use external search, browsing, retrieval, SEC data, Alpha Vantage, "
    "or Fin-Fact evidence.\n\n"
    "Return EXACTLY ONE valid JSON object and nothing else. "
    "The JSON must include exactly these keys in this order: verdict, confidence, explanation. "
    "The verdict must be one of SUPPORTED, REFUTED, or UNVERIFIABLE. "
    "Confidence must be a number between 0.0 and 1.0. "
    "The explanation must be a non-empty string.\n\n"
    "Example: {\"verdict\": \"SUPPORTED\", \"confidence\": 0.6, \"explanation\": \"brief explanation\"}"
)

SYSTEM_PROMPT_B = (
    "You are a financial claim verifier. Use ONLY the supplied evidence below. "
    "Do not use web search, internal knowledge, Fin-Fact evidence, Fin-Fact labels, "
    "or any source other than the supplied evidence. "
    "Classify the claim into exactly one verdict: SUPPORTED, REFUTED, or UNVERIFIABLE. "
    "Return UNVERIFIABLE when the supplied evidence is insufficient or temporally unknown. "
    "Return EXACTLY ONE valid JSON object and nothing else. "
    "The object must have exactly these keys in this order: verdict, confidence, explanation. "
    "Each key is required, and explanation must be a non-empty string. "
    "Confidence is diagnostic only and must be a number from 0.0 to 1.0.\n\n"
    "Example: {\"verdict\": \"UNVERIFIABLE\", \"confidence\": 0.7, \"explanation\": \"The supplied evidence is insufficient to verify this claim.\"}"
)


# ── provider ──────────────────────────────────────────────────────────────────

def _get_ollama_provider():
    """Return local Ollama provider config. No API key needed."""
    return {
        "type": "ollama",
        "api_key": "",
        "model": OLLAMA_MODEL,
        "base_url": OLLAMA_BASE_URL,
    }


# ── error helpers ─────────────────────────────────────────────────────────────

def _safe_error(msg):
    """Redact API keys from error messages before logging."""
    return re.sub(r"([?&]key=)[^&\s]+", r"\1[REDACTED]", str(msg))


def _response_error(response):
    try:
        body = response.json()
        message = (
            body.get("error", {}).get("message")
            or body.get("message")
            or response.reason
        )
    except (ValueError, TypeError):
        message = response.reason
    return _safe_error(f"HTTP {response.status_code}: {message}")


def _retry_delay(response, attempt):
    retry_after = None
    if response is not None:
        retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), 120.0)
        except ValueError:
            pass
    return min(2 ** attempt * 2, 120.0)   # 4, 8, 16, … capped at 120 s


# ── prediction validation ─────────────────────────────────────────────────────

def _validate_prediction(parsed):
    """Validate verdict, confidence, explanation. Raises ValueError on any failure."""
    verdict = str(parsed.get("verdict", "")).strip().upper()
    if verdict not in CLASSES:
        raise ValueError(f"Invalid verdict: {verdict!r}. Must be one of {CLASSES}.")

    confidence = parsed.get("confidence")
    if isinstance(confidence, bool):
        raise ValueError("Confidence must be numeric, not boolean.")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        raise ValueError(f"Confidence is not numeric: {confidence!r}")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"Confidence {confidence} is outside [0.0, 1.0].")

    explanation = parsed.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        for alias in ("reason", "analysis", "summary", "justification", "details", "rationale"):
            if isinstance(parsed.get(alias), str) and parsed[alias].strip():
                explanation = parsed[alias].strip()
                break
    if not isinstance(explanation, str) or not explanation.strip():
        explanation = f"Verdict {verdict} determined based on available information."

    return {
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "explanation": explanation.strip(),
    }


# ── Ollama API call ───────────────────────────────────────────────────────────

def _request_ollama(provider, system_prompt, user_prompt, run_state):
    """Call Ollama OpenAI-compatible chat completions with retry.

    Raises RuntimeError on all unrecoverable failures.
    NEVER silently returns UNVERIFIABLE on API errors.
    """
    payload = {
        "model": provider["model"],
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if provider.get("api_key"):
        headers["Authorization"] = f"Bearer {provider['api_key']}"

    json_mode_enabled = False
    for attempt in range(1, MAX_ATTEMPTS + 1):
        run_state["requests_this_run"] += 1
        try:
            response = requests.post(
                provider["base_url"],
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code in TRANSIENT_STATUS_CODES and attempt < MAX_ATTEMPTS:
                run_state["retry_count"] += 1
                delay = _retry_delay(response, attempt)
                print(f"    [retry {attempt}/{MAX_ATTEMPTS}] HTTP {response.status_code}, "
                      f"waiting {delay:.1f}s …")
                time.sleep(delay)
                continue

            response.raise_for_status()
            data = response.json()
            raw_text = data["choices"][0]["message"]["content"]
            parsed = _parse_llm_json_response(raw_text)
            return _validate_prediction(parsed)

        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status in TRANSIENT_STATUS_CODES and attempt < MAX_ATTEMPTS:
                run_state["retry_count"] += 1
                delay = _retry_delay(exc.response, attempt)
                print(f"    [retry {attempt}/{MAX_ATTEMPTS}] HTTP {status}, "
                      f"waiting {delay:.1f}s …")
                time.sleep(delay)
                continue
            raise RuntimeError(_response_error(exc.response)) from exc

        except requests.RequestException as exc:
            if attempt < MAX_ATTEMPTS:
                run_state["retry_count"] += 1
                delay = min(2 ** attempt * 2, 60)
                print(f"    [retry {attempt}/{MAX_ATTEMPTS}] Network error, "
                      f"waiting {delay:.1f}s …")
                time.sleep(delay)
                continue
            raise RuntimeError(_safe_error(f"Network error: {exc}")) from exc

        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if not json_mode_enabled and attempt < MAX_ATTEMPTS:
                json_mode_enabled = True
                payload["response_format"] = {"type": "json_object"}
                run_state["retry_count"] += 1
                print("    [retry] Invalid response format, retrying with JSON mode")
                continue
            raise RuntimeError(_safe_error(f"Malformed response: {exc}")) from exc

    raise RuntimeError("Ollama request failed after maximum retries")


# ── prompt builders ───────────────────────────────────────────────────────────

def _build_prompt_a(record):
    """Condition A: ONLY claim_text and canonical claim_date — no external evidence."""
    if set(record) != {"claim_id", "claim_text", "claim_date"}:
        raise RuntimeError(f"Unexpected research record fields: {sorted(record)}")
    validate_no_llm_leakage(record)
    date_line = f"Claim date: {record['claim_date']}\n\n" if record.get("claim_date") else ""
    return (
        f"{date_line}"
        f"Claim:\n{record['claim_text']}\n\n"
        "Classify the claim into exactly one of:\n"
        "SUPPORTED\nREFUTED\nUNVERIFIABLE\n\n"
        "Return EXACTLY ONE JSON object with keys in this order: verdict, confidence, explanation. "
        "The explanation must be a non-empty string. "
        "Example: {\"verdict\": \"SUPPORTED\", \"confidence\": 0.6, \"explanation\": \"brief explanation\"}"
    )


def _build_prompt_b(record, evidence):
    """Conditions B1/B2/B3: claim + canonical date + retrieved evidence payload."""
    if set(record) != {"claim_id", "claim_text", "claim_date"}:
        raise RuntimeError(f"Unexpected research record fields: {sorted(record)}")
    validate_no_llm_leakage(record)
    evidence_payload = json.dumps(evidence, ensure_ascii=False)
    return (
        f"Claim ID: {record['claim_id']}\n"
        f"Claim date: {record['claim_date']}\n"
        f"Claim: {record['claim_text']}\n\n"
        f"Supplied evidence: {evidence_payload}\n\n"
        "Return EXACTLY ONE JSON object with keys in this order: verdict, confidence, explanation. "
        "The explanation must be a non-empty string. "
        "Do not omit any required keys or include extra text.\n\n"
        "Example: {\"verdict\": \"UNVERIFIABLE\", \"confidence\": 0.7, \"explanation\": \"The supplied evidence is insufficient to verify this claim.\"}"
    )


# ── evidence retrieval ────────────────────────────────────────────────────────

def _retrieve_sec_for_claim(record, claim_type, entity, cutoff):
    if not entity:
        return [], [{
            "source": "SEC",
            "status": "not_applicable",
            "error": "Company/entity could not be reliably identified.",
        }], False
    if claim_type not in SEC_APPLICABLE_CLAIM_TYPES:
        return [], [{
            "source": "SEC",
            "status": "not_applicable",
            "error": f"Claim type {claim_type!r} is not supported by SEC retrieval.",
        }], False

    evidence, errors = _retrieve_sec_evidence(
        record["claim_text"], claim_type, entity, cutoff
    )
    if not evidence and not errors:
        errors.append({
            "source": "SEC",
            "status": "no_evidence",
            "error": "SEC retrieval returned no evidence for an applicable claim.",
        })
    return evidence, errors, True


def _retrieve_alpha_vantage_for_claim(record, claim_type, entity, cutoff):
    if claim_type != "stock/market movement":
        return [], [{
            "source": "Alpha Vantage",
            "status": "not_applicable",
            "error": f"Claim type {claim_type!r} is not a stock/market-movement claim.",
        }], False
    if not entity:
        return [], [{
            "source": "Alpha Vantage",
            "status": "not_applicable",
            "error": "Company/entity could not be reliably identified.",
        }], False

    av_key = (
        os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
        or os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
    )
    if not av_key:
        return [], [{
            "source": "Alpha Vantage",
            "status": "error",
            "error": "Alpha Vantage API key not configured; source unavailable.",
        }], True

    evidence, errors = _retrieve_alpha_vantage_evidence(
        record["claim_text"], claim_type, entity, cutoff
    )
    if not evidence and not errors:
        errors.append({
            "source": "Alpha Vantage",
            "status": "no_evidence",
            "error": "Alpha Vantage retrieval returned no evidence for an applicable claim.",
        })
    return evidence, errors, True


def _eligible_evidence_items(evidence, cutoff, sources):
    if cutoff is None:
        return []
    eligible = []
    for item in evidence:
        if item.get("source") not in sources or not item.get("evidence_text", "").strip():
            continue
        if not item.get("url") or not item.get("retrieved_at"):
            continue
        try:
            evidence_date = date.fromisoformat(item.get("evidence_date", ""))
        except (TypeError, ValueError):
            continue
        if evidence_date > cutoff:
            continue
        item["temporal_status"] = "valid"
        eligible.append(item)
    return eligible


def _build_evidence(record, sources):
    """Retrieve evidence for B conditions.

    Returns (normalized_evidence, all_source_errors, hard_errors, classification).

    A source is queried only when the claim type and resolved entity make it
    applicable. Applicable sources that return no temporally eligible evidence
    are explicit failures and cannot produce a prediction.
    """
    validate_no_llm_leakage(record)
    classification = _classify_financial_claim(record["claim_text"])
    entity = classification["entity"]
    claim_type = classification["claim_type"]

    try:
        cutoff = date.fromisoformat(record["claim_date"]) if record.get("claim_date") else None
    except (ValueError, TypeError):
        cutoff = None

    evidence = []
    source_errors = []
    applicable_sources = set()
    retrievers = {
        "SEC": _retrieve_sec_for_claim,
        "Alpha Vantage": _retrieve_alpha_vantage_for_claim,
    }
    for source in sources:
        found, errors, applicable = retrievers[source](
            record, claim_type, entity, cutoff
        )
        evidence.extend(found)
        source_errors.extend(errors)
        if applicable:
            applicable_sources.add(source)

    normalized = _normalize_evidence_items(evidence, cutoff)
    normalized = _eligible_evidence_items(normalized, cutoff, sources)

    for source in applicable_sources:
        if not any(item.get("source") == source for item in normalized) and not any(
            item.get("source") == source and item.get("status") in {"error", "no_evidence"}
            for item in source_errors
        ):
            source_errors.append({
                "source": source,
                "status": "no_evidence",
                "error": f"{source} returned no evidence that passed temporal filtering.",
            })

    hard_errors = [
        item for item in source_errors
        if item.get("status") in {"error", "no_evidence"}
    ]

    return normalized, source_errors, hard_errors, classification


def _has_reusable_success(result, sources, condition, record, model):
    if result.get("status") != "success":
        return False
    if (
        result.get("condition") != condition
        or result.get("claim_id") != record["claim_id"]
        or result.get("claim_text") != record["claim_text"]
        or result.get("claim_date") != record.get("claim_date")
        or result.get("provider") != "ollama"
        or result.get("model") != model
        or result.get("sources") != list(sources)
    ):
        return False
    if not sources:
        return True

    evidence_by_source = {
        source: [
            item for item in result.get("evidence", [])
            if item.get("source") == source
            and item.get("evidence_text", "").strip()
            and item.get("temporal_status") == "valid"
            and item.get("url")
            and item.get("retrieved_at")
        ]
        for source in sources
    }
    source_status = result.get("source_status", {})
    if set(source_status) != set(sources):
        return False

    classification = _classify_financial_claim(record["claim_text"])
    entity = classification["entity"]
    claim_type = classification["claim_type"]
    applicable_by_source = {
        "SEC": bool(entity) and claim_type in SEC_APPLICABLE_CLAIM_TYPES,
        "Alpha Vantage": bool(entity) and claim_type == "stock/market movement",
    }
    for source in sources:
        is_applicable = applicable_by_source[source]
        expected_status = "retrieved" if is_applicable else "not_applicable"
        if source_status[source] != expected_status:
            return False
        if is_applicable and not evidence_by_source[source]:
            return False
        if not is_applicable and evidence_by_source[source]:
            return False
    return any(applicable_by_source[source] for source in sources)


def _has_reusable_record(result, sources, condition, record, model):
    if _has_reusable_success(result, sources, condition, record, model):
        return True
    if result.get("status") == "not_applicable":
        if (
            result.get("condition") != condition
            or result.get("claim_id") != record["claim_id"]
            or result.get("claim_text") != record["claim_text"]
            or result.get("claim_date") != record.get("claim_date")
            or result.get("sources") != list(sources)
        ):
            return False
        source_status = result.get("source_status", {})
        if set(source_status) != set(sources):
            return False
        classification = _classify_financial_claim(record["claim_text"])
        entity = classification["entity"]
        claim_type = classification["claim_type"]
        applicable_by_source = {
            "SEC": bool(entity) and claim_type in SEC_APPLICABLE_CLAIM_TYPES,
            "Alpha Vantage": bool(entity) and claim_type == "stock/market movement",
        }
        if any(applicable_by_source[s] for s in sources):
            return False
        if any(source_status[s] != "not_applicable" for s in sources):
            return False
        if result.get("evidence"):
            return False
        return True
    return False


# ── metrics ───────────────────────────────────────────────────────────────────

def _calculate_metrics(results, gold_by_id):
    successful = [r for r in results if r["status"] == "success"]
    if not successful:
        return {"evaluated_claims": 0}
    gold = [LABEL_MAPPING[gold_by_id[r["claim_id"]]] for r in successful]
    predicted = [r["verdict"] for r in successful]
    per_class = {}
    for cls in CLASSES:
        tp = sum(a == cls and p == cls for a, p in zip(gold, predicted))
        fp = sum(a != cls and p == cls for a, p in zip(gold, predicted))
        fn = sum(a == cls and p != cls for a, p in zip(gold, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall    = tp / (tp + fn) if tp + fn else 0.0
        f1        = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[cls] = {"precision": round(precision, 4),
                          "recall": round(recall, 4),
                          "f1": round(f1, 4)}
    confusion = {a: {p: 0 for p in CLASSES} for a in CLASSES}
    for a, p in zip(gold, predicted):
        confusion[a][p] += 1
    accuracy = sum(a == p for a, p in zip(gold, predicted)) / len(successful)
    return {
        "evaluated_claims": len(successful),
        "accuracy": round(accuracy, 4),
        "macro_precision": round(sum(v["precision"] for v in per_class.values()) / 3, 4),
        "macro_recall":    round(sum(v["recall"]    for v in per_class.values()) / 3, 4),
        "macro_f1":        round(sum(v["f1"]        for v in per_class.values()) / 3, 4),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "predicted_class_counts": {cls: predicted.count(cls) for cls in CLASSES},
    }


# ── file I/O ──────────────────────────────────────────────────────────────────

def _load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ── main runner ───────────────────────────────────────────────────────────────

def run_condition(condition_name):
    config = CONDITION_CONFIGS[condition_name]
    result_path   = config["result_path"]
    progress_path = config["progress_path"]
    sources       = config["sources"]

    # ── sanity checks ────────────────────────────────────────────────────────
    sample     = _load_json(SAMPLE_PATH)
    evaluation = _load_json(EVALUATION_PATH)

    if len(sample) != 300 or len(evaluation) != 300:
        raise RuntimeError(
            "Fixed research sample and evaluation must each contain exactly 300 records."
        )
    sample_ids = [r["claim_id"] for r in sample]
    eval_ids   = [r["claim_id"] for r in evaluation]
    if len(set(sample_ids)) != 300:
        raise RuntimeError("Fixed research sample must contain exactly 300 unique claim IDs.")
    if sample_ids != eval_ids:
        raise RuntimeError("Sample and evaluation claim IDs are not aligned.")

    gold_by_id = {r["claim_id"]: r["gold_label"] for r in evaluation}
    if set(gold_by_id.values()) != set(LABEL_MAPPING):
        raise RuntimeError(f"Unexpected evaluation labels: {set(gold_by_id.values())}")

    # ── provider check ───────────────────────────────────────────────────────
    provider = _get_ollama_provider()
    # Verify Ollama is reachable
    try:
        _r = requests.get("http://localhost:11434/api/tags", timeout=5)
        _r.raise_for_status()
    except requests.RequestException:
        raise RuntimeError(
            "Cannot connect to Ollama at localhost:11434. "
            "Start the server with: C:\\Users\\vishn\\Ollama\\ollama.exe serve"
        )

    print(f"\n{'='*60}")
    print(f"CONDITION {condition_name}")
    print(f"Provider : {provider['type']}")
    print(f"Model    : {provider['model']}")
    print(f"Sources  : {list(sources) or '(none — internal knowledge only)'}")
    print(f"Results  : {result_path.name}")
    print(f"{'='*60}")

    # ── load existing (resumable) ─────────────────────────────────────────────
    existing = []
    if result_path.exists():
        existing = _load_json(result_path)
    existing_by_id = {
        item["claim_id"]: item
        for item in existing
        if item["claim_id"] in set(sample_ids)
    }

    results = []
    for record in sample:
        cid = record["claim_id"]
        prev = existing_by_id.get(cid)
        if prev and _has_reusable_record(
            prev, sources, condition_name, record, provider["model"]
        ):
            results.append(prev)
        else:
            base = {
                "condition":   condition_name,
                "claim_id":    cid,
                "claim_text":  record["claim_text"],
                "claim_date":  record.get("claim_date"),
                "provider":    provider["type"],
                "model":       provider["model"],
                "sources":     list(sources),
                "verdict":     None,
                "confidence":  None,
                "explanation": None,
                "status":      "error",
                "error":       None,
            }
            if sources:
                base.update({
                    "evidence":      [],
                    "source_errors": [],
                    "claim_type":    None,
                    "entity":        None,
                })
            results.append(base)

    already_success = sum(1 for r in results if r["status"] == "success")
    already_na = sum(1 for r in results if r["status"] == "not_applicable")
    print(f"Resuming from {already_success} grounded successes, {already_na} not applicable ({already_success + already_na}/300 processed).\n")

    # ── main loop ────────────────────────────────────────────────────────────
    run_state = {"requests_this_run": 0, "retry_count": 0}

    for index, record in enumerate(sample):
        result = results[index]
        if result["status"] in {"success", "not_applicable"}:
            continue

        cid = record["claim_id"]
        llm_record = {
            "claim_id":   cid,
            "claim_text": record["claim_text"],
            "claim_date": record.get("claim_date"),
        }

        try:
            if sources:
                evidence, source_errors, hard_errors, classification = _build_evidence(
                    llm_record, sources
                )
                source_status = {}
                for source in sources:
                    if any(item.get("source") == source for item in evidence):
                        source_status[source] = "retrieved"
                    else:
                        matching_errors = [
                            item for item in source_errors if item.get("source") == source
                        ]
                        source_status[source] = (
                            matching_errors[-1].get("status", "error")
                            if matching_errors else "no_evidence"
                        )
                result.update(
                    evidence=evidence,
                    source_errors=source_errors,
                    source_status=source_status,
                    claim_type=classification["claim_type"],
                    entity=(
                        classification["entity"]["name"]
                        if classification["entity"] else None
                    ),
                )
                # Hard retrieval errors prevent prediction — they must NOT become UNVERIFIABLE
                if hard_errors:
                    raise RuntimeError(
                        "Evidence retrieval hard error: "
                        + json.dumps(hard_errors, ensure_ascii=False)
                    )
                if evidence:
                    user_prompt   = _build_prompt_b(llm_record, evidence)
                    system_prompt = SYSTEM_PROMPT_B
                else:
                    result.update(status="not_applicable", error=None)
            else:
                user_prompt   = _build_prompt_a(llm_record)
                system_prompt = SYSTEM_PROMPT_A

            if result["status"] != "not_applicable":
                prediction = _request_ollama(
                    provider, system_prompt, user_prompt, run_state
                )
                result.update(**prediction, status="success", error=None)

        except Exception as exc:
            err_msg = _safe_error(exc)
            result.update(
                verdict=None, confidence=None, explanation=None,
                status="error", error=err_msg,
            )

        _save(result_path, results)
        successful = sum(1 for item in results if item["status"] == "success")
        not_applicable = sum(1 for item in results if item["status"] == "not_applicable")
        failed = sum(1 for item in results if item["status"] == "error" and item.get("error"))
        _save(progress_path, {
            "condition": condition_name,
            "sources": list(sources),
            "provider": provider["type"],
            "model": provider["model"],
            "total_claims": 300,
            "successful": successful,
            "not_applicable": not_applicable,
            "failed": failed,
            "remaining": 300 - (successful + not_applicable + failed),
            "requests_this_run": run_state["requests_this_run"],
            "retry_count": run_state["retry_count"],
            "status": "in_progress",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "api_errors_distinct": sorted({
                item["error"] for item in results if item.get("error")
            }),
            "retrieval_coverage": {
                "total_claims": 300,
                "applicable_claims": sum(1 for r in results if r.get("status") in {"success", "error"}),
                "evidence_retrieved": successful,
                "not_applicable": not_applicable,
                "retrieval_failures": failed,
            },
            "metrics": _calculate_metrics(results, gold_by_id),
        })
        time.sleep(INTER_REQUEST_DELAY)

        # Progress report every 25 claims
        if (index + 1) % 25 == 0:
            done = sum(1 for r in results if r["status"] in {"success", "not_applicable"})
            s_done = sum(1 for r in results if r["status"] == "success")
            print(f"  [{condition_name}] claim {index+1:3d}/300 processed | "
                  f"{done}/300 accounted for ({s_done} grounded) | "
                  f"{run_state['requests_this_run']} API calls this run")

    # ── final save ───────────────────────────────────────────────────────────
    successful = sum(1 for r in results if r["status"] == "success")
    not_applicable = sum(1 for r in results if r["status"] == "not_applicable")
    failed     = sum(1 for r in results if r["status"] == "error" and r.get("error"))

    status_str = "complete" if (successful + not_applicable == 300 and failed == 0) else "batch_complete"
    progress = {
        "condition":           condition_name,
        "sources":             list(sources),
        "provider":            provider["type"],
        "model":               provider["model"],
        "total_claims":        300,
        "successful":          successful,
        "not_applicable":      not_applicable,
        "failed":              failed,
        "remaining":           300 - (successful + not_applicable + failed),
        "requests_this_run":   run_state["requests_this_run"],
        "retry_count":         run_state["retry_count"],
        "status":              status_str,
        "timestamp":           datetime.now(timezone.utc).isoformat(),
        "api_errors_distinct": sorted({
            r["error"] for r in results if r.get("error")
        }),
        "retrieval_coverage": {
            "total_claims": 300,
            "applicable_claims": sum(1 for r in results if r.get("status") in {"success", "error"}),
            "evidence_retrieved": successful,
            "not_applicable": not_applicable,
            "retrieval_failures": failed,
        },
        "metrics":             _calculate_metrics(results, gold_by_id),
    }

    _save(result_path, results)
    _save(progress_path, progress)

    print(f"\n[{condition_name}] COMPLETE: {successful}/300 successful | "
          f"{failed} failed | status={status_str}")
    return progress


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CONDITION_CONFIGS:
        print(f"Usage: python {Path(__file__).name} <condition>")
        print(f"Available conditions: {', '.join(CONDITION_CONFIGS)}")
        sys.exit(1)

    cond = sys.argv[1]
    result = run_condition(cond)
    summary = {
        "condition":  result["condition"],
        "model":      result["model"],
        "successful": result["successful"],
        "failed":     result["failed"],
        "remaining":  result["remaining"],
        "status":     result["status"],
    }
    if result.get("metrics") and result["metrics"].get("evaluated_claims", 0) > 0:
        summary["accuracy"]         = result["metrics"]["accuracy"]
        summary["macro_precision"]  = result["metrics"]["macro_precision"]
        summary["macro_recall"]     = result["metrics"]["macro_recall"]
        summary["macro_f1"]         = result["metrics"]["macro_f1"]
    print("\n" + json.dumps(summary, indent=2))
    sys.exit(0 if result["successful"] == 300 else 1)
