import json
import re

sample = json.load(open("data/finfact_research_sample.json", encoding="utf-8"))

keywords = [
    "target", "amazon", "apple", "google", "microsoft", "disney", "boeing",
    "tesla", "netflix", "walmart", "costco", "starbucks", "mcdonald", "coca-cola",
    "coke", "nike", "ford", "gm", "general motors", "chevron", "exxon", "pfizer",
    "moderna", "johnson", "bank of america", "wells fargo", "citigroup", "jpmorgan",
    "goldman", "morgan stanley", "att", "at&t", "verizon", "intel", "amd", "nvidia",
    "uber", "lyft", "airbnb", "ebay", "paypal", "visa", "mastercard"
]

found = []
for i, item in enumerate(sample):
    text = item["claim_text"]
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            found.append((i, item["claim_id"], kw, text))

print(f"Total matches found: {len(found)}")
for m in found:
    print(f"[{m[0]}] {m[1]} ({m[2]}): {m[3]}")
