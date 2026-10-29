import json, os, sys

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
V2_DIR = os.path.join(DATA_DIR, "experiment_v2")

conditions = {
    "A":  "condition_a_ollama_qwen25_3b_results.json",
    "B1": "condition_b1_ollama_qwen25_3b_results.json",
    "B2": "condition_b2_ollama_qwen25_3b_results.json",
    "B3": "condition_b3_ollama_qwen25_3b_results.json",
}

def print_run_status(title, target_dir):
    print(f"\n{'='*55}\n{title} ({target_dir})\n{'='*55}")
    for k, v in conditions.items():
        path = os.path.join(target_dir, v)
        if os.path.exists(path):
            try:
                data = json.load(open(path, "r", encoding="utf-8"))
                s = sum(1 for r in data if r.get("status") == "success")
                na = sum(1 for r in data if r.get("status") == "not_applicable")
                e = sum(1 for r in data if r.get("status") == "error" and r.get("error"))
                print(f"{k}: {s:3d} grounded successes, {na:3d} not applicable, {e:3d} errors (total {len(data)})")
            except Exception as ex:
                print(f"{k}: error reading file ({ex})")
        else:
            print(f"{k}: not started")

if __name__ == "__main__":
    if "--v2" in sys.argv:
        print_run_status("Experiment v2", V2_DIR)
    elif "--v1" in sys.argv:
        print_run_status("Original Runs (v1)", DATA_DIR)
    else:
        print_run_status("Experiment v2 (Latest Grounded Run)", V2_DIR)
        print_run_status("Original Runs v1 (Preserved Baseline)", DATA_DIR)
