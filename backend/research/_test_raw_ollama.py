import json
import requests
import sys

data = json.load(open("data/condition_b1_ollama_qwen25_3b_results.json", encoding="utf-8"))
r = data[43]

sys.path.insert(0, ".")
from research.run_openai_experiment_300 import (
    _parse_llm_json_response,
    _validate_prediction
)

system_prompt = (
    "You are a financial claim verifier. Use ONLY the supplied evidence below. "
    "Do not use web search, internal knowledge, Fin-Fact evidence, Fin-Fact labels, "
    "or any source other than the supplied evidence. "
    "Classify the claim into exactly one verdict: SUPPORTED, REFUTED, or UNVERIFIABLE. "
    "Return UNVERIFIABLE when the supplied evidence is insufficient or temporally unknown. "
    "Return EXACTLY ONE valid JSON object and nothing else. "
    "The object must have exactly these keys in this order: verdict, confidence, explanation. "
    "The explanation must be a non-empty string explaining the decision. "
    "Confidence is diagnostic only and must be a number from 0.0 to 1.0.\n\n"
    "Example: {\"verdict\": \"UNVERIFIABLE\", \"confidence\": 0.7, \"explanation\": \"The evidence mentions shareholder meetings and equity details but does not discuss nationwide store closures.\"}"
)

user_prompt = (
    f"Claim ID: {r['claim_id']}\n"
    f"Claim date: {r['claim_date']}\n"
    f"Claim: {r['claim_text']}\n\n"
    f"Supplied evidence: {json.dumps(r['evidence'], ensure_ascii=False)}\n\n"
    "Return EXACTLY ONE JSON object with keys in this order: verdict, confidence, explanation. "
    "The explanation must be a non-empty string. "
    "Example: {\"verdict\": \"UNVERIFIABLE\", \"confidence\": 0.7, \"explanation\": \"brief explanation\"}"
)

payload = {
    "model": "qwen2.5:3b",
    "temperature": 0.0,
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
}

resp = requests.post("http://localhost:11434/v1/chat/completions", json=payload, timeout=60)
raw = resp.json()["choices"][0]["message"]["content"]
print("RAW OUTPUT:")
print(raw)
print("\nPARSED:")
parsed = _parse_llm_json_response(raw)
print(parsed)
val = _validate_prediction(parsed)
print("VALIDATED:", val)
