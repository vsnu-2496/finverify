"""One-claim Ollama/qwen2.5:3b smoke test for the Fin-Fact research experiment.

Verifies: provider init, API call, JSON parsing, verdict validation,
confidence validation, leakage protection, and error handling.

Uses the local Ollama OpenAI-compatible endpoint at localhost:11434.
No API key required.
"""

import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── project path setup ────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from app import _parse_llm_json_response
from data.finfact_loader import validate_no_llm_leakage

# ── constants ─────────────────────────────────────────────────────────────────
SAMPLE_PATH = BACKEND_DIR / "data" / "finfact_research_sample.json"
CLASSES = ("SUPPORTED", "REFUTED", "UNVERIFIABLE")
REQUEST_TIMEOUT = (10, 300)  # generous timeout for local CPU inference

OLLAMA_BASE_URL = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "qwen2.5:3b"

SYSTEM_PROMPT = (
    "You are verifying a financial claim using only your internal knowledge.\n\n"
    "Classify the claim into exactly one of:\n"
    "SUPPORTED\n"
    "REFUTED\n"
    "UNVERIFIABLE\n\n"
    "SUPPORTED = the claim is consistent with your knowledge.\n"
    "REFUTED = the claim contradicts reliable knowledge.\n"
    "UNVERIFIABLE = there is insufficient information to determine whether "
    "it is true or false.\n\n"
    "Do not use external search, browsing, retrieval, SEC data, "
    "Alpha Vantage, or Fin-Fact evidence.\n\n"
    "Return JSON only:\n"
    '{"verdict": "SUPPORTED | REFUTED | UNVERIFIABLE", "confidence": 0.0, '
    '"explanation": "brief explanation"}\n\n'
    "Confidence must be a number between 0.0 and 1.0. "
    "It is the model's self-reported confidence for the predicted verdict, "
    "not a calibrated probability."
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_ollama_provider():
    """Return the local Ollama provider config. No API key needed."""
    return {
        "type": "ollama",
        "api_key": "",
        "model": OLLAMA_MODEL,
        "base_url": OLLAMA_BASE_URL,
    }


def _build_llm_record(raw):
    """Extract exactly the three permitted research fields."""
    return {
        "claim_id": raw["claim_id"],
        "claim_text": raw["claim_text"],
        "claim_date": raw.get("claim_date"),
    }


def _build_prompt(record):
    """Return user prompt containing ONLY claim_text and canonical claim_date."""
    if set(record) != {"claim_id", "claim_text", "claim_date"}:
        raise RuntimeError(
            f"Unexpected research record fields: {sorted(record)}"
        )
    validate_no_llm_leakage(record)
    date_line = (
        f"Claim date: {record['claim_date']}\n\n"
        if record.get("claim_date") else ""
    )
    return (
        f"{date_line}"
        f"Claim:\n{record['claim_text']}\n\n"
        "Classify the claim into exactly one of:\n"
        "SUPPORTED\nREFUTED\nUNVERIFIABLE\n\n"
        "Return JSON only:\n"
        '{"verdict": "SUPPORTED | REFUTED | UNVERIFIABLE", "confidence": 0.0, '
        '"explanation": "brief explanation"}'
    )


def _call_ollama(provider, system_prompt, user_prompt):
    """POST to Ollama OpenAI-compatible endpoint. Raises on any error."""
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

    response = requests.post(
        provider["base_url"],
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _validate_prediction(parsed):
    """Validate verdict and confidence. Raises ValueError on invalid values."""
    verdict = str(parsed.get("verdict", "")).strip().upper()
    if verdict not in CLASSES:
        raise ValueError(
            f"Invalid verdict: {verdict!r}. Must be one of {CLASSES}."
        )

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
        raise ValueError("Explanation must be a non-empty string.")

    return {
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "explanation": explanation.strip(),
    }


def _verify_error_handling():
    """Structural check: errors must raise, not silently return UNVERIFIABLE."""
    import inspect
    src = inspect.getsource(_call_ollama)
    if "raise_for_status" not in src:
        raise RuntimeError("_call_ollama does not call raise_for_status()")
    flagged = [
        line for line in src.splitlines()
        if "return" in line and "UNVERIFIABLE" in line
    ]
    if flagged:
        raise RuntimeError(
            f"_call_ollama returns UNVERIFIABLE as fallback: {flagged}"
        )


# ── main smoke test ───────────────────────────────────────────────────────────

def run_smoke_test():
    results = {
        "provider": "Ollama (local)",
        "model": OLLAMA_MODEL,
        "claim_id": None,
        "api_status":            "FAIL",
        "json_parsing":          "FAIL",
        "label_validation":      "FAIL",
        "confidence_validation": "FAIL",
        "leakage_check":         "FAIL",
        "error_handling":        "FAIL",
        "prediction": None,
        "error_message": None,
    }

    # ── Step 1: Load one claim ────────────────────────────────────────────────
    with SAMPLE_PATH.open("r", encoding="utf-8") as f:
        sample = json.load(f)
    raw = sample[0]

    # ── Step 2: Build leakage-safe LLM input ─────────────────────────────────
    llm_record = _build_llm_record(raw)
    results["claim_id"] = llm_record["claim_id"]

    # ── Step 3: Leakage check ────────────────────────────────────────────────
    try:
        validate_no_llm_leakage(llm_record)
        forbidden = {
            "gold_label", "label", "evidence", "justification", "issues",
            "author", "url", "hrefs", "image_data", "sci_digest",
            "visualization_bias",
        }
        leaking = forbidden & set(llm_record)
        if leaking:
            raise ValueError(f"Leakage fields present: {sorted(leaking)}")
        results["leakage_check"] = "PASS"
    except Exception as exc:
        results["error_message"] = f"Leakage check failed: {exc}"
        return results

    # ── Step 4: Provider init ────────────────────────────────────────────────
    provider = _get_ollama_provider()
    results["model"] = provider["model"]

    # ── Step 5: Build prompt ──────────────────────────────────────────────────
    try:
        user_prompt = _build_prompt(llm_record)
    except Exception as exc:
        results["error_message"] = f"Prompt construction failed: {exc}"
        return results

    # ── Step 6: API call ──────────────────────────────────────────────────────
    raw_text = None
    try:
        print(f"  Calling Ollama (qwen2.5:3b) — this may take 30-60s on CPU...")
        raw_text = _call_ollama(provider, SYSTEM_PROMPT, user_prompt)
        results["api_status"] = "PASS"
    except requests.ConnectionError:
        results["error_message"] = (
            "Cannot connect to Ollama at localhost:11434. "
            "Is 'ollama serve' running?"
        )
        return results
    except requests.HTTPError as exc:
        results["error_message"] = f"HTTP error: {exc}"
        return results
    except requests.RequestException as exc:
        results["error_message"] = f"Network error: {exc}"
        return results
    except Exception as exc:
        results["error_message"] = f"Unexpected error: {exc}"
        return results

    # ── Step 7: JSON parsing ──────────────────────────────────────────────────
    try:
        parsed = _parse_llm_json_response(raw_text)
        results["json_parsing"] = "PASS"
    except (json.JSONDecodeError, ValueError) as exc:
        results["error_message"] = (
            f"JSON parse error: {exc} | raw={raw_text[:300]!r}"
        )
        return results

    # ── Step 8: Label + confidence validation ─────────────────────────────────
    try:
        prediction = _validate_prediction(parsed)
        results["label_validation"]      = "PASS"
        results["confidence_validation"] = "PASS"
        results["prediction"]            = prediction
    except ValueError as exc:
        results["error_message"] = str(exc)
        return results

    # ── Step 9: Error-handling verification ───────────────────────────────────
    try:
        _verify_error_handling()
        results["error_handling"] = "PASS"
    except Exception as exc:
        results["error_message"] = f"Error-handling check failed: {exc}"
        return results

    return results


if __name__ == "__main__":
    r = run_smoke_test()

    all_checks = [
        r["api_status"],
        r["json_parsing"],
        r["label_validation"],
        r["confidence_validation"],
        r["leakage_check"],
        r["error_handling"],
    ]
    overall = "PASS" if all(c == "PASS" for c in all_checks) else "FAIL"

    print("\n" + "=" * 52)
    print("SMOKE TEST RESULT")
    print("=" * 52)
    print(f"Provider:              {r['provider']}")
    print(f"Model:                 {r['model']}")
    print(f"Claim ID:              {r['claim_id'] or 'unknown'}")
    print(f"API status:            {r['api_status']}")
    print(f"JSON parsing:          {r['json_parsing']}")
    print(f"Label validation:      {r['label_validation']}")
    print(f"Confidence validation: {r['confidence_validation']}")
    print(f"Leakage check:         {r['leakage_check']}")
    print(f"Error handling:        {r['error_handling']}")
    print(f"Overall smoke test:    {overall}")
    print("=" * 52)

    if r.get("prediction"):
        p = r["prediction"]
        print(f"\nPrediction:")
        print(f"  Verdict:     {p['verdict']}")
        print(f"  Confidence:  {p['confidence']}")
        print(f"  Explanation: {p['explanation'][:200]}")

    if r.get("error_message"):
        print(f"\nError: {r['error_message']}")

    sys.exit(0 if overall == "PASS" else 1)
