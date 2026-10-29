import json
from pathlib import Path

DATA_DIR = Path("data")

for cond in ["A", "B1", "B2"]:
    path = DATA_DIR / f"condition_{cond.lower()}_ollama_qwen25_3b_results.json"
    if not path.exists():
        print(f"[{cond}] File does not exist")
        continue
    data = json.load(path.open("r", encoding="utf-8"))
    total = len(data)
    success = sum(1 for r in data if r.get("status") == "success")
    errors = sum(1 for r in data if r.get("status") == "error")
    with_evidence = sum(1 for r in data if len(r.get("evidence", [])) > 0)
    verdicts = {}
    for r in data:
        v = r.get("verdict")
        verdicts[v] = verdicts.get(v, 0) + 1
    print(f"[{cond}] Total: {total}, Success: {success}, Errors: {errors}, With Evidence: {with_evidence}, Verdicts: {verdicts}")
