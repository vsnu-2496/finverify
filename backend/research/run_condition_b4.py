"""
run_condition_b4.py

Runner for Condition B4: Retrospective Fact-Check Evidence Synthesis.
Evaluates external news and fact-checking evidence for LLM-based financial news claim verification.

Core Safeguards:
1. Manifest verification: Verifies SHA-256 integrity of protected benchmark and v1/v2 files before and after execution.
2. 4-tier pipeline accounting:
   grounded_success + no_relevant_evidence + retrieval_error + inference_error == 300
3. Leakage filter: Conservative, auditable filter distinguishing primary sources, neutral reporting, verdict leakage, and uncertain leakage.
4. Verbatim evidence retention: Evidence is never rewritten or fabricated; rejected items record explicit reasons.
5. Dry-run mode (--dry-run): Runs full retrieval, temporal checking, relevance gating, and leakage filtering without calling Ollama or any external APIs.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from research.canonical_mapping import (
    CLASSES,
    LABEL_MAPPING,
    PIPELINE_STATUSES,
    STATUS_GROUNDED_SUCCESS,
    STATUS_INFERENCE_ERROR,
    STATUS_NO_RELEVANT_EVIDENCE,
    STATUS_RETRIEVAL_ERROR,
    RETRIEVAL_SUCCESS,
    RETRIEVAL_NO_RESULTS,
    RETRIEVAL_TECHNICAL_ERROR,
    RELEVANCE_RELEVANT,
    RELEVANCE_IRRELEVANT,
    verify_manifest,
)
from research.news_evidence_retriever import (
    BenchmarkNewsRetriever,
    check_temporal_setting,
    evaluate_news_relevance,
)
from research.leakage_filter import (
    filter_evidence_items,
    LEAKAGE_PRIMARY_SOURCE,
    LEAKAGE_FACT_CHECKER_REPORTING,
    LEAKAGE_VERDICT_LEAKAGE,
    LEAKAGE_UNCERTAIN,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

EXPERIMENTAL_CONDITION_LABEL = "B4_retrospective_fact_check_evidence_synthesis"
TEMPORAL_POLICY_RATIONALE = (
    "Claim posted date corresponds to fact-check publication date rather than original "
    "claim utterance date; post-claim retrospective synthesis is evaluated with explicit leak filtering."
)


def load_dataset(sample_path: Path) -> List[Dict[str, Any]]:
    with open(sample_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_b4_prompt(claim_text: str, evidence_items: List[Dict[str, Any]]) -> str:
    """
    Constructs strict, evidence-grounded prompt for Qwen2.5:3b.
    Evidence excerpts are verbatim without modification.
    """
    evidence_block = ""
    for i, item in enumerate(evidence_items, start=1):
        src = item.get("source_name", "Source")
        date_str = item.get("publication_date", "Undated")
        text = item.get("retrieved_text", "").strip()
        evidence_block += f"[{i}] ({src}, {date_str}): {text}\n"

    prompt = (
        f"You are an expert financial news verifier. Your task is to verify whether the following "
        f"financial news claim is SUPPORTED, REFUTED, or UNVERIFIABLE based strictly on the provided evidence.\n\n"
        f"Claim: \"{claim_text}\"\n\n"
        f"Retrieved Evidence:\n{evidence_block}\n"
        f"Instructions:\n"
        f"- Output 'SUPPORTED' if the evidence directly confirms the claim.\n"
        f"- Output 'REFUTED' if the evidence directly contradicts or disproves the claim.\n"
        f"- Output 'UNVERIFIABLE' if the evidence is insufficient, ambiguous, or does not address the claim.\n"
        f"- Format your response as a JSON object with keys 'verdict' (one of SUPPORTED, REFUTED, UNVERIFIABLE) "
        f"and 'explanation' (brief reasoning).\n"
    )
    return prompt


def parse_and_validate_llm_response(raw_text: str) -> Dict[str, Any]:
    """
    Parses and strictly validates the JSON response from Qwen2.5:3b.
    Expected format:
    {
        "verdict": "SUPPORTED" | "REFUTED" | "UNVERIFIABLE",
        "explanation": "..."
    }
    Raises ValueError on parsing failure or disallowed label.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Empty response received from LLM.")

    text = raw_text.strip()
    # Strip markdown code blocks if present
    code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_match:
        text = code_match.group(1).strip()
    else:
        # Fallback to finding outermost JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as ex:
        raise ValueError(f"Failed to parse LLM response as JSON: {ex}; raw text: {raw_text[:200]!r}")

    if not isinstance(parsed, dict):
        raise ValueError(f"LLM JSON response must be an object/dict, got {type(parsed).__name__}")

    raw_verdict = parsed.get("verdict")
    if not raw_verdict or not isinstance(raw_verdict, str):
        raise ValueError(f"Missing or non-string 'verdict' in LLM response: {parsed}")

    verdict = raw_verdict.strip().upper()
    if verdict not in CLASSES:
        raise ValueError(f"Invalid verdict label: {verdict!r}. Must be one of {CLASSES}.")

    explanation = parsed.get("explanation")
    if not explanation or not isinstance(explanation, str):
        explanation = f"Verdict {verdict} determined based on provided evidence."
    else:
        explanation = explanation.strip()

    confidence = parsed.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
            if not 0.0 <= confidence <= 1.0:
                confidence = 1.0
        except (ValueError, TypeError):
            confidence = 1.0
    else:
        confidence = 1.0

    return {
        "verdict": verdict,
        "explanation": explanation,
        "confidence": round(confidence, 3),
        "raw_response": raw_text,
    }


def request_ollama_inference(
    prompt: str,
    model: str = "qwen2.5:3b",
    base_url: str = "http://localhost:11434/v1/chat/completions",
    max_retries: int = 3,
    timeout: int = 60,
    retry_delay: float = 2.0,
    requester_fn: Optional[Any] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Calls Ollama chat completion API with bounded retries and temperature 0.0.
    Returns (raw_response_text, validated_prediction_dict).
    Raises RuntimeError on failure after all retries exhausted.
    """
    payload = {
        "model": model,
        "temperature": 0.0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict financial news verification engine. "
                    "Analyze the claim and provided evidence, then return a valid JSON object with "
                    "keys 'verdict' (one of SUPPORTED, REFUTED, UNVERIFIABLE) and 'explanation'."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            if requester_fn is not None:
                raw_text = requester_fn(payload, attempt=attempt)
            else:
                response = requests.post(base_url, json=payload, timeout=timeout)
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
                data = response.json()
                raw_text = data["choices"][0]["message"]["content"]

            validated = parse_and_validate_llm_response(raw_text)
            return raw_text, validated

        except Exception as ex:
            last_error = ex
            logger.warning(
                "Ollama inference attempt %d/%d failed: %s",
                attempt,
                max_retries,
                str(ex),
            )
            if attempt < max_retries and retry_delay > 0:
                time.sleep(min(retry_delay * attempt, 10))

    raise RuntimeError(f"Inference failed after {max_retries} attempts. Last error: {last_error}")


def save_progress_atomic(
    progress_path: Path,
    records: List[Dict[str, Any]],
    status_counts: Dict[str, int],
    leakage_stats: Dict[str, int],
    temporal_setting: str,
    dry_run: bool,
) -> None:
    """
    Atomically writes current progress records to disk.
    """
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = progress_path.with_suffix(".tmp")
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "experimental_condition": EXPERIMENTAL_CONDITION_LABEL,
        "temporal_setting": temporal_setting,
        "total_claims": 300,
        "completed_count": len(records),
        "status_accounting": status_counts,
        "leakage_filter_statistics": leakage_stats,
        "records": records,
    }
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    temp_file.replace(progress_path)


def process_claim_evidence(
    claim: Dict[str, Any],
    retriever: BenchmarkNewsRetriever,
    temporal_setting: str = "retrospective",
) -> Dict[str, Any]:
    """
    Retrieves, checks temporal validity, evaluates semantic relevance,
    and applies conservative leakage filtering for a single claim.
    """
    claim_id = claim["claim_id"]
    claim_text = claim["claim_text"]
    claim_date = claim.get("claim_date")

    # Step 1: Benchmark retrieval
    ret_res = retriever.retrieve_for_claim(claim_id)
    ret_status = ret_res.get("retrieval_status", RETRIEVAL_TECHNICAL_ERROR)
    raw_items = ret_res.get("evidence_items", [])

    if ret_status == RETRIEVAL_TECHNICAL_ERROR:
        return {
            "retrieval_status": RETRIEVAL_TECHNICAL_ERROR,
            "pipeline_status": STATUS_RETRIEVAL_ERROR,
            "error_message": ret_res.get("error_message"),
            "raw_items_count": 0,
            "accepted_evidence": [],
            "rejected_evidence": [],
        }

    if not raw_items:
        return {
            "retrieval_status": ret_status,
            "pipeline_status": STATUS_NO_RELEVANT_EVIDENCE,
            "error_message": None,
            "raw_items_count": 0,
            "accepted_evidence": [],
            "rejected_evidence": [],
        }

    # Step 2: Temporal & Relevance Gating
    gated_candidates = []
    rejected_at_gating = []

    for item in raw_items:
        ev_text = item.get("retrieved_text", "")
        ev_date = item.get("publication_date")

        # Temporal check
        temp_check = check_temporal_setting(ev_date, claim_date, setting=temporal_setting)
        if not temp_check["is_temporally_valid"]:
            rejected_item = dict(item)
            rejected_item["rejection_stage"] = "temporal_filter"
            rejected_item["rejection_reason"] = temp_check["reason"]
            rejected_at_gating.append(rejected_item)
            continue

        # Semantic relevance check
        rel_check = evaluate_news_relevance(claim_text, ev_text)
        if not rel_check["is_relevant"]:
            rejected_item = dict(item)
            rejected_item["rejection_stage"] = "relevance_gate"
            rejected_item["rejection_reason"] = rel_check["reason"]
            rejected_item["matched_anchors"] = rel_check["matched_anchors"]
            rejected_at_gating.append(rejected_item)
            continue

        # Passed temporal and relevance
        item_copy = dict(item)
        item_copy["temporal_info"] = temp_check
        item_copy["relevance_info"] = rel_check
        gated_candidates.append(item_copy)

    # Step 3: Conservative leakage filtering
    accepted_items, leakage_rejected = filter_evidence_items(gated_candidates)

    for rej in leakage_rejected:
        rej["rejection_stage"] = "leakage_filter"

    all_rejected = rejected_at_gating + leakage_rejected

    if len(accepted_items) == 0:
        pipeline_status = STATUS_NO_RELEVANT_EVIDENCE
    else:
        pipeline_status = STATUS_GROUNDED_SUCCESS

    return {
        "retrieval_status": ret_status,
        "pipeline_status": pipeline_status,
        "error_message": None,
        "raw_items_count": len(raw_items),
        "accepted_evidence": accepted_items,
        "rejected_evidence": all_rejected,
    }


def run_pipeline(
    sample_path: Path,
    output_path: Path,
    audit_path: Path,
    dry_run: bool = True,
    temporal_setting: str = "retrospective",
    progress_path: Optional[Path] = None,
    resume: bool = True,
    checkpoint_interval: int = 1,
    model_name: str = "qwen2.5:3b",
    ollama_url: str = "http://localhost:11434/v1/chat/completions",
    retry_delay: float = 2.0,
    requester_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes the B4 pipeline across the 300-claim research sample.
    """
    # Safeguard 1: Pre-run manifest verification
    logger.info("Executing pre-run SHA-256 manifest verification...")
    manifest_ok, manifest_report = verify_manifest()
    if not manifest_ok:
        logger.error("Pre-run manifest verification failed: %s", manifest_report)
        raise RuntimeError("Pre-run manifest verification failed! Protected files have been altered or are missing.")
    logger.info("Pre-run manifest verified successfully.")

    # Load 300 claims
    claims = load_dataset(sample_path)
    logger.info("Loaded %d claims from %s", len(claims), sample_path)
    if len(claims) != 300:
        raise ValueError(f"Expected exactly 300 claims, found {len(claims)}")

    retriever = BenchmarkNewsRetriever()

    results: List[Dict[str, Any]] = []
    status_counts = {
        STATUS_GROUNDED_SUCCESS: 0,
        STATUS_NO_RELEVANT_EVIDENCE: 0,
        STATUS_RETRIEVAL_ERROR: 0,
        STATUS_INFERENCE_ERROR: 0,
    }

    leakage_stats = {
        "total_raw_evidence_items": 0,
        "rejected_temporal": 0,
        "rejected_relevance": 0,
        "rejected_verdict_leakage": 0,
        "rejected_uncertain_leakage": 0,
        "accepted_primary_source": 0,
        "accepted_fact_checker_reporting": 0,
    }

    completed_ids = set()

    # Safe resume logic from atomic progress checkpoint
    if resume and progress_path and progress_path.exists():
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                prog_data = json.load(f)
            saved_records = prog_data.get("records", [])
            for r in saved_records:
                cid = r.get("claim_id")
                p_status = r.get("pipeline_status")
                if cid and p_status in status_counts:
                    results.append(r)
                    completed_ids.add(cid)
                    status_counts[p_status] += 1
                    raw_count = r.get("raw_evidence_count", 0)
                    leakage_stats["total_raw_evidence_items"] += raw_count
                    for item in r.get("accepted_evidence", []):
                        if item.get("leakage_classification") == LEAKAGE_PRIMARY_SOURCE:
                            leakage_stats["accepted_primary_source"] += 1
                        else:
                            leakage_stats["accepted_fact_checker_reporting"] += 1
                    for rej in r.get("rejected_evidence", []):
                        stage = rej.get("rejection_stage")
                        if stage == "temporal_filter":
                            leakage_stats["rejected_temporal"] += 1
                        elif stage == "relevance_gate":
                            leakage_stats["rejected_relevance"] += 1
                        elif stage == "leakage_filter":
                            c = rej.get("leakage_classification")
                            if c == LEAKAGE_VERDICT_LEAKAGE:
                                leakage_stats["rejected_verdict_leakage"] += 1
                            elif c == LEAKAGE_UNCERTAIN:
                                leakage_stats["rejected_uncertain_leakage"] += 1
            logger.info("Resumed %d claims from progress checkpoint %s", len(results), progress_path)
        except Exception as ex:
            logger.warning("Failed to load progress file %s: %s; starting fresh.", progress_path, ex)
            results = []
            completed_ids = set()
            status_counts = {k: 0 for k in status_counts}
            leakage_stats = {k: 0 for k in leakage_stats}

    for idx, claim in enumerate(claims):
        claim_id = claim["claim_id"]
        if claim_id in completed_ids:
            continue

        claim_text = claim["claim_text"]
        claim_date = claim.get("claim_date")
        author = claim.get("author")

        ev_proc = process_claim_evidence(claim, retriever, temporal_setting=temporal_setting)
        pipe_status = ev_proc["pipeline_status"]

        raw_count = ev_proc["raw_items_count"]
        leakage_stats["total_raw_evidence_items"] += raw_count

        accepted = ev_proc["accepted_evidence"]
        rejected = ev_proc["rejected_evidence"]

        # Track audit rejection/acceptance counts
        for item in accepted:
            c = item.get("leakage_classification")
            if c == LEAKAGE_PRIMARY_SOURCE:
                leakage_stats["accepted_primary_source"] += 1
            else:
                leakage_stats["accepted_fact_checker_reporting"] += 1

        for rej in rejected:
            stage = rej.get("rejection_stage")
            if stage == "temporal_filter":
                leakage_stats["rejected_temporal"] += 1
            elif stage == "relevance_gate":
                leakage_stats["rejected_relevance"] += 1
            elif stage == "leakage_filter":
                c = rej.get("leakage_classification")
                if c == LEAKAGE_VERDICT_LEAKAGE:
                    leakage_stats["rejected_verdict_leakage"] += 1
                elif c == LEAKAGE_UNCERTAIN:
                    leakage_stats["rejected_uncertain_leakage"] += 1

        # Determine verdict and explanation
        if pipe_status == STATUS_NO_RELEVANT_EVIDENCE:
            verdict = "UNVERIFIABLE"
            explanation = "No relevant, non-leaking evidence survived gating. Pipeline abstained."
            confidence = 0.0
            error = None
        elif pipe_status == STATUS_RETRIEVAL_ERROR:
            verdict = "UNVERIFIABLE"
            explanation = f"Retrieval technical error: {ev_proc.get('error_message')}"
            confidence = 0.0
            error = ev_proc.get("error_message")
        elif pipe_status == STATUS_GROUNDED_SUCCESS:
            if dry_run:
                verdict = "DRY_RUN_PENDING"
                explanation = f"Dry-run simulation: {len(accepted)} evidence items passed gating and leakage filter."
                confidence = 0.0
                error = None
            else:
                # Full inference mode
                prompt = build_b4_prompt(claim_text, accepted)
                try:
                    raw_resp, parsed = request_ollama_inference(
                        prompt,
                        model=model_name,
                        base_url=ollama_url,
                        max_retries=3,
                        retry_delay=retry_delay,
                        requester_fn=requester_fn,
                    )
                    verdict = parsed["verdict"]
                    confidence = parsed.get("confidence", 1.0)
                    explanation = parsed.get("explanation", "")
                    error = None
                except Exception as ex:
                    # Do NOT convert inference error into UNVERIFIABLE or GROUNDED_SUCCESS
                    pipe_status = STATUS_INFERENCE_ERROR
                    verdict = "INFERENCE_ERROR"
                    confidence = 0.0
                    explanation = f"Inference execution failed: {str(ex)}"
                    error = str(ex)
        else:
            verdict = "UNVERIFIABLE"
            explanation = "Unknown pipeline status."
            confidence = 0.0
            error = "Unknown pipeline status"

        status_counts[pipe_status] += 1

        record = {
            "condition": "B4",
            "experimental_condition": EXPERIMENTAL_CONDITION_LABEL,
            "claim_id": claim_id,
            "claim_text": claim_text,
            "claim_date": claim_date,
            "author": author,
            "provider": "ollama",
            "model": model_name,
            "sources": ["benchmark_archive"],
            "retrieval_status": ev_proc["retrieval_status"],
            "retrieval_method": "benchmark_archive",
            "temporal_setting": temporal_setting,
            "temporal_rationale": TEMPORAL_POLICY_RATIONALE,
            "pipeline_status": pipe_status,
            "verdict": verdict,
            "confidence": confidence,
            "explanation": explanation,
            "error": error,
            "raw_evidence_count": raw_count,
            "accepted_evidence_count": len(accepted),
            "rejected_evidence_count": len(rejected),
            "accepted_evidence": accepted,
            "rejected_evidence": rejected,
        }
        results.append(record)
        completed_ids.add(claim_id)

        # Periodic atomic progress checkpointing
        if progress_path and not dry_run and (len(results) % checkpoint_interval == 0):
            save_progress_atomic(
                progress_path,
                results,
                status_counts,
                leakage_stats,
                temporal_setting,
                dry_run,
            )

    # Invariant Check: Sum of 4 statuses MUST equal 300
    total_accounted = sum(status_counts.values())
    if total_accounted != 300:
        raise AssertionError(f"Accounting mismatch: sum of statuses is {total_accounted}, expected 300!")

    audit_summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "experimental_condition": EXPERIMENTAL_CONDITION_LABEL,
        "total_claims": 300,
        "status_accounting": status_counts,
        "coverage_metrics": {
            "evidence_coverage_rate": round(status_counts[STATUS_GROUNDED_SUCCESS] / 300.0, 4),
            "abstention_rate": round(status_counts[STATUS_NO_RELEVANT_EVIDENCE] / 300.0, 4),
            "retrieval_error_rate": round(status_counts[STATUS_RETRIEVAL_ERROR] / 300.0, 4),
            "inference_error_rate": round(status_counts[STATUS_INFERENCE_ERROR] / 300.0, 4),
        },
        "leakage_filter_statistics": leakage_stats,
    }

    # Write output and audit files
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info("Saved %d claim records to %s", len(results), output_path)

    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, indent=2)
    logger.info("Saved audit summary to %s", audit_path)

    # Update final checkpoint on complete run
    if progress_path and not dry_run:
        save_progress_atomic(
            progress_path,
            results,
            status_counts,
            leakage_stats,
            temporal_setting,
            dry_run,
        )

    # Safeguard 2: Post-run manifest verification
    logger.info("Executing post-run SHA-256 manifest verification...")
    post_ok, post_report = verify_manifest()
    if not post_ok:
        logger.error("Post-run manifest verification failed: %s", post_report)
        raise RuntimeError("Post-run manifest verification failed! Protected files have been altered!")
    logger.info("Post-run manifest verified successfully. All protected files are intact.")

    return audit_summary


def main():
    parser = argparse.ArgumentParser(description="Run Condition B4 for Financial News Claim Verification")
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Run dry run without calling LLM (default: True)",
    )
    parser.add_argument(
        "--run-inference",
        dest="dry_run",
        action="store_false",
        help="Execute real Ollama inference (disables dry-run)",
    )
    parser.add_argument(
        "--temporal-setting",
        "--setting",
        dest="temporal_setting",
        choices=["retrospective", "prospective"],
        default="retrospective",
        help="Temporal evaluation setting (default: retrospective)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        default=False,
        help="Do not resume from progress file",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=1,
        help="Checkpoint save frequency in claims (default: 1)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    sample_path = project_root / "backend" / "data" / "finfact_research_sample.json"
    exp_v3_dir = project_root / "backend" / "data" / "experiment_v3"
    exp_v3_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        output_path = exp_v3_dir / "condition_b4_dry_run_results.json"
        audit_path = exp_v3_dir / "b4_dry_run_audit.json"
        progress_path = None
    else:
        output_path = exp_v3_dir / "condition_b4_results.json"
        audit_path = exp_v3_dir / "b4_inference_audit.json"
        progress_path = exp_v3_dir / "condition_b4_progress.json"

    mode_name = "Dry Run" if args.dry_run else "Full Inference"
    logger.info("Starting Condition B4 %s (temporal=%s)...", mode_name, args.temporal_setting)
    summary = run_pipeline(
        sample_path=sample_path,
        output_path=output_path,
        audit_path=audit_path,
        dry_run=args.dry_run,
        temporal_setting=args.temporal_setting,
        progress_path=progress_path,
        resume=not args.no_resume,
        checkpoint_interval=args.checkpoint_interval,
    )
    print(f"\n=== Condition B4 {mode_name} Summary ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
