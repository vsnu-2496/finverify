import json
import os
import sys
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")
sys.path.insert(0, ".")
from app import _classify_financial_claim, _retrieve_sec_evidence, SEC_COMPANIES

sample = json.load(open("data/finfact_research_sample.json", encoding="utf-8"))

target_indices = [43, 63, 83, 145, 184]
for idx in target_indices:
    item = sample[idx]
    c = _classify_financial_claim(item["claim_text"])
    cutoff = date.fromisoformat(item["claim_date"]) if item.get("claim_date") else None
    print(f"\n--- Testing Index {idx}: {item['claim_id']} ({item['claim_date']}) ---")
    print(f"Claim: {item['claim_text']}")
    print(f"Entity: {c['entity']['name']}, Type: {c['claim_type']}")
    
    evidence, errors = _retrieve_sec_evidence(item["claim_text"], c["claim_type"], c["entity"], cutoff)
    print(f"Evidence count: {len(evidence)}")
    if evidence:
        for ev in evidence:
            print("  Found evidence:", ev["source"], ev["evidence_date"], ev["url"])
            print("  Snippet:", ev["evidence_text"][:150])
    if errors:
        for err in errors:
            print("  Error:", err)
