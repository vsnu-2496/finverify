import json
import sys
from pathlib import Path
import shutil

sys.path.insert(0, ".")
from research.config import CLASSES, LABEL_MAPPING
from research.run_openai_experiment_300 import _calculate_metrics

DATA_DIR = Path("data")
B3_RESULTS_PATH = DATA_DIR / "condition_b3_ollama_qwen25_3b_results.json"
B3_PROGRESS_PATH = DATA_DIR / "condition_b3_ollama_qwen25_3b_progress.json"
SAMPLE_PATH = DATA_DIR / "finfact_research_sample.json"
EVAL_PATH = DATA_DIR / "finfact_research_evaluation.json"

sample = json.load(open(SAMPLE_PATH, encoding="utf-8"))
eval_data = json.load(open(EVAL_PATH, encoding="utf-8"))
b3_results = json.load(open(B3_RESULTS_PATH, encoding="utf-8"))
b3_progress = json.load(open(B3_PROGRESS_PATH, encoding="utf-8"))

print("=== STEP 3: B3 INTEGRITY AUDIT ===")
print("Total sample records:", len(sample))
print("Total eval records:", len(eval_data))
print("Total B3 results records:", len(b3_results))

sample_ids = [r["claim_id"] for r in sample]
b3_ids = [r["claim_id"] for r in b3_results]
assert len(b3_results) == 300, f"Expected 300 records, got {len(b3_results)}"
assert len(set(b3_ids)) == 300, f"Expected 300 unique IDs, got {len(set(b3_ids))}"
assert sample_ids == b3_ids, "Sample and B3 claim IDs do not match in order"

status_counts = {}
for r in b3_results:
    s = r.get("status")
    status_counts[s] = status_counts.get(s, 0) + 1
print("\nStatus distribution in B3:", status_counts)
assert status_counts.get("success") == 5, f"Expected 5 success, got {status_counts.get('success')}"
assert status_counts.get("not_applicable") == 295, f"Expected 295 not_applicable, got {status_counts.get('not_applicable')}"
assert status_counts.get("error", 0) == 0, f"Expected 0 error, got {status_counts.get('error')}"

gold_by_id = {r["claim_id"]: r["gold_label"] for r in eval_data}
evaluated = [r for r in b3_results if r.get("status") == "success"]
print("\n--- 5 Evaluated Claims Detail (B3 Combined) ---")
for r in evaluated:
    cid = r["claim_id"]
    gold_raw = gold_by_id[cid]
    gold_norm = LABEL_MAPPING[gold_raw]
    pred = r["verdict"]
    conf = r["confidence"]
    ev_count = len(r.get("evidence", []))
    print(f"\nClaim ID: {cid}")
    print(f"Claim: {r['claim_text']}")
    print(f"Gold: {gold_raw} -> {gold_norm} | Pred: {pred} (conf: {conf})")
    print(f"Match: {gold_norm == pred}")
    print(f"Evidence items: {ev_count}")
    for item in r.get("evidence", []):
        print(f"  - Source: {item.get('source')}, Date: {item.get('evidence_date')}, URL: {item.get('url')}")
    print(f"Explanation: {r['explanation']}")

recomputed_metrics = _calculate_metrics(b3_results, gold_by_id)
print("\n--- Recomputed B3 Metrics ---")
print("Evaluated Claims:", recomputed_metrics["evaluated_claims"])
print("Accuracy:", recomputed_metrics["accuracy"])
print("Macro Precision:", recomputed_metrics["macro_precision"])
print("Macro Recall:", recomputed_metrics["macro_recall"])
print("Macro F1:", recomputed_metrics["macro_f1"])
print("Confusion Matrix:")
for actual, row in recomputed_metrics["confusion_matrix"].items():
    print(f"  {actual:12s}: {row}")

backup_dir = DATA_DIR / "backups" / "b3_validated_complete_20261019"
backup_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2(B3_RESULTS_PATH, backup_dir / B3_RESULTS_PATH.name)
shutil.copy2(B3_PROGRESS_PATH, backup_dir / B3_PROGRESS_PATH.name)
print(f"\nB3 backed up to {backup_dir}")
