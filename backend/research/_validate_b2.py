import json
import sys
from pathlib import Path
import shutil

DATA_DIR = Path("data")
B2_RESULTS_PATH = DATA_DIR / "condition_b2_ollama_qwen25_3b_results.json"
B2_PROGRESS_PATH = DATA_DIR / "condition_b2_ollama_qwen25_3b_progress.json"
SAMPLE_PATH = DATA_DIR / "finfact_research_sample.json"

sample = json.load(open(SAMPLE_PATH, encoding="utf-8"))
b2_results = json.load(open(B2_RESULTS_PATH, encoding="utf-8"))
b2_progress = json.load(open(B2_PROGRESS_PATH, encoding="utf-8"))

print("=== STEP 2: B2 INTEGRITY AUDIT ===")
print("Total sample records:", len(sample))
print("Total B2 results records:", len(b2_results))

sample_ids = [r["claim_id"] for r in sample]
b2_ids = [r["claim_id"] for r in b2_results]
assert len(b2_results) == 300, f"Expected 300 records, got {len(b2_results)}"
assert len(set(b2_ids)) == 300, f"Expected 300 unique IDs, got {len(set(b2_ids))}"
assert sample_ids == b2_ids, "Sample and B2 claim IDs do not match in order"

status_counts = {}
for r in b2_results:
    s = r.get("status")
    status_counts[s] = status_counts.get(s, 0) + 1
print("\nStatus distribution in B2:", status_counts)

print("Progress JSON content:")
print(json.dumps(b2_progress, indent=2))

backup_dir = DATA_DIR / "backups" / "b2_validated_complete_20261019"
backup_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2(B2_RESULTS_PATH, backup_dir / B2_RESULTS_PATH.name)
shutil.copy2(B2_PROGRESS_PATH, backup_dir / B2_PROGRESS_PATH.name)
print(f"\nB2 backed up to {backup_dir}")
