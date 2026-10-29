"""
smoke_test_b4_3claims.py

Controlled, non-destructive 3-claim smoke test harness for Condition B4.
Selects exactly one claim from each canonical reference class (SUPPORTED, REFUTED, UNVERIFIABLE).
Saves outputs strictly to a dedicated smoke_test directory.
Ensures zero gold-label leakage in prompts and verifies JSON response parsing.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from research.canonical_mapping import (
    CLASSES,
    LABEL_MAPPING,
    STATUS_GROUNDED_SUCCESS,
    STATUS_INFERENCE_ERROR,
    STATUS_NO_RELEVANT_EVIDENCE,
    STATUS_RETRIEVAL_ERROR,
    verify_manifest,
)
from research.news_evidence_retriever import (
    BenchmarkNewsRetriever,
    check_temporal_setting,
    evaluate_news_relevance,
)
from research.leakage_filter import filter_evidence_items
from research.run_condition_b4 import (
    build_b4_prompt,
    parse_and_validate_llm_response,
    process_claim_evidence,
    request_ollama_inference,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
SAMPLE_FILE = DATA_DIR / "finfact_research_sample.json"
EVALUATION_FILE = DATA_DIR / "finfact_research_evaluation.json"
SMOKE_OUTPUT_DIR = DATA_DIR / "smoke_test"


def select_stratified_smoke_claims(
    sample_path: Path = SAMPLE_FILE,
    eval_path: Path = EVALUATION_FILE,
    prefer_grounded: bool = True,
) -> List[Dict[str, Any]]:
    """
    Selects exactly one claim for each class: SUPPORTED, REFUTED, UNVERIFIABLE.
    Uses evaluation file strictly to identify reference class, not for inference.
    """
    with open(sample_path, "r", encoding="utf-8") as f:
        claims = json.load(f)

    with open(eval_path, "r", encoding="utf-8") as f:
        eval_records = json.load(f)

    eval_map = {r["claim_id"]: r["gold_label"] for r in eval_records}

    # Load dry run to know which claims have surviving evidence
    dry_run_path = DATA_DIR / "experiment_v3" / "condition_b4_dry_run_results.json"
    grounded_cids = set()
    if prefer_grounded and dry_run_path.exists():
        with open(dry_run_path, "r", encoding="utf-8") as f:
            dry_data = json.load(f)
        grounded_cids = {r["claim_id"] for r in dry_data if r.get("pipeline_status") == STATUS_GROUNDED_SUCCESS}

    selected = {}
    # First pass: try to pick grounded claims for each class
    for c in claims:
        cid = c["claim_id"]
        raw_gold = eval_map.get(cid)
        canonical_gold = LABEL_MAPPING.get(raw_gold, raw_gold)
        if canonical_gold in CLASSES and canonical_gold not in selected:
            if not prefer_grounded or cid in grounded_cids:
                claim_copy = dict(c)
                claim_copy["_eval_reference_class"] = canonical_gold
                selected[canonical_gold] = claim_copy
        if len(selected) == len(CLASSES):
            break

    # Second pass: fill any remaining classes
    for c in claims:
        cid = c["claim_id"]
        raw_gold = eval_map.get(cid)
        canonical_gold = LABEL_MAPPING.get(raw_gold, raw_gold)
        if canonical_gold in CLASSES and canonical_gold not in selected:
            claim_copy = dict(c)
            claim_copy["_eval_reference_class"] = canonical_gold
            selected[canonical_gold] = claim_copy
        if len(selected) == len(CLASSES):
            break

    # Return in canonical order [SUPPORTED, REFUTED, UNVERIFIABLE]
    return [selected[cls] for cls in CLASSES if cls in selected]


def run_smoke_test(
    sample_path: Path = SAMPLE_FILE,
    output_dir: Path = SMOKE_OUTPUT_DIR,
    run_inference: bool = False,
    requester_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes controlled 3-claim smoke test with zero impact on benchmark files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "b4_smoke_results.json"
    audit_file = output_dir / "b4_smoke_audit.json"

    # 1. Pre-run manifest verification
    manifest_ok, manifest_rep = verify_manifest()
    if not manifest_ok:
        raise RuntimeError(f"Pre-run manifest verification failed: {manifest_rep}")
    logger.info("Pre-run manifest verified: 7 protected files intact.")

    smoke_claims = select_stratified_smoke_claims(sample_path)
    logger.info("Selected %d stratified claims for smoke testing.", len(smoke_claims))

    retriever = BenchmarkNewsRetriever()
    results = []
    status_counts = {
        STATUS_GROUNDED_SUCCESS: 0,
        STATUS_NO_RELEVANT_EVIDENCE: 0,
        STATUS_RETRIEVAL_ERROR: 0,
        STATUS_INFERENCE_ERROR: 0,
    }

    for claim in smoke_claims:
        cid = claim["claim_id"]
        ctext = claim["claim_text"]
        gold_canonical = claim.get("_eval_reference_class")

        # Process evidence through temporal, relevance, and leakage gates
        ev_proc = process_claim_evidence(claim, retriever, temporal_setting="retrospective")
        p_status = ev_proc["pipeline_status"]
        accepted = ev_proc["accepted_evidence"]

        # Safeguard: ensure prompt NEVER receives the gold label
        prompt = build_b4_prompt(ctext, accepted)
        assert f"Gold: {gold_canonical}" not in prompt
        assert f"label: {gold_canonical}" not in prompt

        verdict = "DRY_RUN_PENDING"
        confidence = 0.0
        explanation = ""
        error_msg = None

        if p_status == STATUS_NO_RELEVANT_EVIDENCE:
            verdict = "UNVERIFIABLE"
            explanation = "No relevant, non-leaking evidence survived gating. Pipeline abstained."
            status_counts[STATUS_NO_RELEVANT_EVIDENCE] += 1
        elif p_status == STATUS_RETRIEVAL_ERROR:
            verdict = "UNVERIFIABLE"
            explanation = f"Retrieval error: {ev_proc.get('error_message')}"
            error_msg = ev_proc.get("error_message")
            status_counts[STATUS_RETRIEVAL_ERROR] += 1
        elif p_status == STATUS_GROUNDED_SUCCESS:
            if run_inference:
                try:
                    _, parsed = request_ollama_inference(
                        prompt=prompt,
                        model="qwen2.5:3b",
                        requester_fn=requester_fn,
                        max_retries=2,
                        retry_delay=0.5,
                    )
                    verdict = parsed["verdict"]
                    confidence = parsed["confidence"]
                    explanation = parsed["explanation"]
                    status_counts[STATUS_GROUNDED_SUCCESS] += 1
                except Exception as ex:
                    p_status = STATUS_INFERENCE_ERROR
                    verdict = "INFERENCE_ERROR"
                    explanation = f"Inference failed: {ex}"
                    error_msg = str(ex)
                    status_counts[STATUS_INFERENCE_ERROR] += 1
            else:
                verdict = "DRY_RUN_PENDING"
                explanation = f"Dry-run smoke test: {len(accepted)} evidence items passed gating."
                status_counts[STATUS_GROUNDED_SUCCESS] += 1

        results.append({
            "claim_id": cid,
            "claim_text": ctext,
            "reference_class_eval_only": gold_canonical,
            "pipeline_status": p_status,
            "verdict": verdict,
            "confidence": confidence,
            "explanation": explanation,
            "error_message": error_msg,
            "evidence_count": len(accepted),
            "evidence_snippets": [item["retrieved_text"][:120] for item in accepted],
        })

    # Save isolated smoke test outputs
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    audit_summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "smoke_test": True,
        "mode": "live_inference" if run_inference else "dry_run",
        "claims_evaluated": len(results),
        "status_accounting": status_counts,
        "accounting_invariant_holds": sum(status_counts.values()) == len(results),
    }

    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, indent=2)

    # Post-run manifest verification
    post_ok, post_rep = verify_manifest()
    if not post_ok:
        raise RuntimeError(f"Post-run manifest verification failed: {post_rep}")
    logger.info("Post-run manifest verified: protected files untouched.")

    return audit_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Condition B4 3-Claim Smoke Test")
    parser.add_argument("--run-inference", action="store_true", help="Attempt live Ollama inference")
    args = parser.parse_args()

    summary = run_smoke_test(run_inference=args.run_inference)
    print("\n=== Smoke Test Summary ===")
    print(json.dumps(summary, indent=2))
