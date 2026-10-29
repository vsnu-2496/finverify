import json
from pathlib import Path
import sys

DATA_DIR = Path("data")
SAMPLE_PATH = DATA_DIR / "finfact_research_sample.json"
EVAL_PATH = DATA_DIR / "finfact_research_evaluation.json"

sys.path.insert(0, ".")
from research.config import CLASSES, LABEL_MAPPING
from research.run_openai_experiment_300 import _calculate_metrics

sample = json.load(open(SAMPLE_PATH, encoding="utf-8"))
eval_data = json.load(open(EVAL_PATH, encoding="utf-8"))
gold_by_id = {r["claim_id"]: r["gold_label"] for r in eval_data}
sample_ids = [r["claim_id"] for r in sample]

conditions = {
    "A": DATA_DIR / "condition_a_ollama_qwen25_3b_results.json",
    "B1": DATA_DIR / "condition_b1_ollama_qwen25_3b_results.json",
    "B2": DATA_DIR / "condition_b2_ollama_qwen25_3b_results.json",
    "B3": DATA_DIR / "condition_b3_ollama_qwen25_3b_results.json",
}

print("=== 1. FILE INTEGRITY & UNIQUE CLAIM CHECKS ===")
audit_results = {}
for cond, path in conditions.items():
    assert path.exists(), f"File {path} does not exist"
    data = json.load(open(path, encoding="utf-8"))
    ids = [r["claim_id"] for r in data]
    total = len(data)
    unique_ids = len(set(ids))
    status_counts = {}
    for r in data:
        st = r.get("status")
        status_counts[st] = status_counts.get(st, 0) + 1
    
    assert total == 300, f"Expected 300 in {cond}, got {total}"
    assert unique_ids == 300, f"Expected 300 unique IDs in {cond}, got {unique_ids}"
    assert ids == sample_ids, f"ID order mismatch in {cond}"
    
    metrics = _calculate_metrics(data, gold_by_id)
    audit_results[cond] = {
        "total": total,
        "unique_ids": unique_ids,
        "status_counts": status_counts,
        "metrics": metrics,
    }
    print(f"\nCondition {cond}:")
    print(f"  Total records: {total}, Unique IDs: {unique_ids}")
    print(f"  Status counts: {status_counts}")
    print(f"  Evaluated claims: {metrics.get('evaluated_claims', 0)}")
    if metrics.get("evaluated_claims", 0) > 0:
        print(f"  Accuracy: {metrics['accuracy']:.4f}")
        print(f"  Macro-F1: {metrics['macro_f1']:.4f}")
        print(f"  Confusion Matrix: {metrics['confusion_matrix']}")

print("\n=== 2. SEMANTIC RELEVANCE AUDIT OF RETRIEVED SEC EVIDENCE ===")
for cond in ["B1", "B3"]:
    data = json.load(open(conditions[cond], encoding="utf-8"))
    evaluated = [r for r in data if r.get("status") == "success"]
    print(f"\nCondition {cond} Evaluated Claims Evidence Semantic Audit:")
    for r in evaluated:
        print(f"\n[{r['claim_id']}] Claim: {r['claim_text']}")
        print(f"Entity: {r.get('entity')}, Type: {r.get('claim_type')}")
        print(f"Model Prediction: {r.get('verdict')} (conf: {r.get('confidence')})")
        print(f"Explanation: {r.get('explanation')}")
        for ev in r.get("evidence", []):
            print(f"  - Source: {ev.get('source')}, Date: {ev.get('evidence_date')}, URL: {ev.get('url')}")
            print(f"    Text snippet: {ev.get('evidence_text')[:140]}...")
