import json
import re

sample = json.load(open("data/finfact_research_sample.json", encoding="utf-8"))

print(f"Total claims: {len(sample)}")
# Look for potential corporate or financial terms
companies_seen = []
for i, item in enumerate(sample):
    text = item["claim_text"]
    # Check for words like stock, shares, company names, etc.
    if re.search(r"\b(stock|shares|shares of|nasdaq|nyse|dow|s&p|inc\.|corp|corporation|bank|general motors|boeing|disney|tesla|google|alphabet|exxon|chevron|target|jpmorgan|goldman|wells fargo|citigroup|uber|lyft|netflix|nike|starbucks|moderna|johnson & johnson|general electric|ge|gm|att|at&t|verizon)\b", text, re.IGNORECASE):
        companies_seen.append((i, item["claim_id"], item["claim_date"], text))

print(f"Claims with corporate/market terms: {len(companies_seen)}")
for c in companies_seen[:30]:
    print(f"[{c[0]}] {c[1]} ({c[2]}): {c[3]}")
