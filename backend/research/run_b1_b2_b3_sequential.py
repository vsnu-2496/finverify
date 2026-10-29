"""Run B1, B2, B3 sequentially. Resumes from where each left off."""
import subprocess
import sys
import json
import os

PYTHON = sys.executable
RUNNER = os.path.join(os.path.dirname(__file__), "run_openai_experiment_300.py")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

CONDITIONS = ["B1", "B2", "B3"]
RESULT_FILES = {
    "B1": "condition_b1_ollama_qwen25_3b_results.json",
    "B2": "condition_b2_ollama_qwen25_3b_results.json",
    "B3": "condition_b3_ollama_qwen25_3b_results.json",
}


def count_processed(condition):
    path = os.path.join(DATA_DIR, RESULT_FILES[condition])
    if not os.path.exists(path):
        return 0, 0, 0
    data = json.load(open(path, "r", encoding="utf-8"))
    s = sum(1 for r in data if r.get("status") == "success")
    na = sum(1 for r in data if r.get("status") == "not_applicable")
    e = sum(1 for r in data if r.get("status") == "error" and r.get("error"))
    return s, na, e


for cond in CONDITIONS:
    s, na, e = count_processed(cond)
    total_accounted = s + na
    if total_accounted >= 300 and e == 0:
        print(f"\n[{cond}] Already complete ({s} grounded, {na} not applicable, 0 errors). Skipping.")
        continue

    print(f"\n{'='*60}")
    print(f"Starting {cond} (currently {s} grounded, {na} not applicable, {e} errors)")
    print(f"{'='*60}")

    result = subprocess.run(
        [PYTHON, RUNNER, cond],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )

    s_final, na_final, e_final = count_processed(cond)
    final_accounted = s_final + na_final
    print(f"\n[{cond}] Finished: {s_final} grounded, {na_final} not applicable, {e_final} errors (exit code {result.returncode})")

    if final_accounted < 300 or e_final > 0:
        print(f"[{cond}] WARNING: {300 - final_accounted} unaddressed claims or {e_final} errors remaining.")
        print(f"[{cond}] Stopping before the next condition to preserve sequential order.")
        break

# Final summary
print(f"\n{'='*60}")
print("FINAL STATUS")
print(f"{'='*60}")

all_conditions = {
    "A": "condition_a_ollama_qwen25_3b_results.json",
    **RESULT_FILES,
}
for cond, fname in all_conditions.items():
    path = os.path.join(DATA_DIR, fname)
    if os.path.exists(path):
        data = json.load(open(path, "r", encoding="utf-8"))
        s = sum(1 for r in data if r.get("status") == "success")
        na = sum(1 for r in data if r.get("status") == "not_applicable")
        e = sum(1 for r in data if r.get("status") == "error" and r.get("error"))
        print(f"  {cond}: {s} grounded successes, {na} not applicable, {e} errors (total {len(data)})")
    else:
        print(f"  {cond}: not started")
