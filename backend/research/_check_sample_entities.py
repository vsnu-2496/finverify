import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from app import _classify_financial_claim, SEC_COMPANIES

sample = json.load(open("data/finfact_research_sample.json", encoding="utf-8"))
print("Total sample claims:", len(sample))

matched_entities = []
claim_types = {}
for i, item in enumerate(sample):
    c = _classify_financial_claim(item["claim_text"])
    ct = c["claim_type"]
    claim_types[ct] = claim_types.get(ct, 0) + 1
    if c["entity"]:
        matched_entities.append((i, item["claim_id"], item["claim_date"], c["entity"]["name"], ct, item["claim_text"][:60]))

print("\nClaim types distribution:")
for ct, count in sorted(claim_types.items(), key=lambda x: x[1], reverse=True):
    print(f"  {ct}: {count}")

print(f"\nClaims matching SEC_COMPANIES entities: {len(matched_entities)}")
for e in matched_entities:
    print(f"  Index {e[0]}: {e[1]} ({e[2]}) [{e[3]}] ({e[4]}): {e[5]}...")
