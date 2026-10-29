"""Prepare leakage-free train, validation, and test splits for the pretrained classifier.

Design rules:
1. The 300 claims in `backend/data/finfact_research_sample.json` serve as the test set,
   ensuring an exact, direct, apples-to-apples comparison with Model A (Qwen2.5:3b).
2. The remaining claims from `finfact.json` are deduplicated and checked against the test set
   to strictly prevent data leakage (any overlapping claim texts are removed).
3. The remaining clean training pool is split into Train (85%) and Validation (15%) using
   stratified sampling with random seed 42.
4. Target labels: SUPPORTED, REFUTED, UNVERIFIABLE.
"""

import json
import re
from pathlib import Path
from collections import Counter

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
ROOT_DIR = BACKEND_DIR.parent
FINFACT_PATH = ROOT_DIR / "finfact.json"
TEST_SAMPLE_PATH = DATA_DIR / "finfact_research_sample.json"
TEST_EVAL_PATH = DATA_DIR / "finfact_research_evaluation.json"

LABEL_MAPPING = {
    "true": "SUPPORTED",
    "false": "REFUTED",
    "NEI": "UNVERIFIABLE",
    "SUPPORTED": "SUPPORTED",
    "REFUTED": "REFUTED",
    "UNVERIFIABLE": "UNVERIFIABLE",
}


def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def main():
    print("=" * 60)
    print("PREPARING CLASSIFIER DATA SPLITS (LEAKAGE-FREE)")
    print("=" * 60)

    # 1. Load test set (the 300-claim research sample)
    with TEST_SAMPLE_PATH.open("r", encoding="utf-8") as f:
        test_samples = json.load(f)
    with TEST_EVAL_PATH.open("r", encoding="utf-8") as f:
        test_evals = json.load(f)

    test_eval_map = {item["claim_id"]: item["gold_label"] for item in test_evals}

    test_records = []
    test_texts_norm = set()
    test_ids = set()

    for item in test_samples:
        cid = item["claim_id"]
        raw_label = test_eval_map.get(cid)
        norm_label = LABEL_MAPPING.get(raw_label)
        if not norm_label:
            raise ValueError(f"Unknown test label {raw_label} for {cid}")
        text = item["claim_text"].strip()
        test_records.append({
            "claim_id": cid,
            "claim_text": text,
            "claim_date": item.get("claim_date"),
            "label": norm_label,
            "split": "test",
        })
        test_ids.add(cid)
        test_texts_norm.add(normalize_text(text))

    print(f"Loaded held-out test set: {len(test_records)} claims")
    print(f"Test label distribution: {Counter(r['label'] for r in test_records)}")

    # 2. Load entire Fin-Fact dataset
    with FINFACT_PATH.open("r", encoding="utf-8") as f:
        raw_finfact = json.load(f)

    print(f"Total raw Fin-Fact records: {len(raw_finfact)}")

    # 3. Filter and deduplicate pool
    pool = []
    skipped_test_id = 0
    skipped_test_text = 0
    skipped_invalid_label = 0
    seen_pool_texts = set()

    for idx, row in enumerate(raw_finfact, start=1):
        cid = f"finfact_{idx:06d}"
        raw_label = row.get("label")
        norm_label = LABEL_MAPPING.get(raw_label)
        if not norm_label:
            skipped_invalid_label += 1
            continue

        claim_text = str(row.get("claim", "")).strip()
        if not claim_text:
            continue

        norm_text = normalize_text(claim_text)

        # Leakage check: is this claim in the test set?
        if cid in test_ids:
            skipped_test_id += 1
            continue
        if norm_text in test_texts_norm:
            skipped_test_text += 1
            continue

        # Pool deduplication
        if norm_text in seen_pool_texts:
            continue
        seen_pool_texts.add(norm_text)

        pool.append({
            "claim_id": cid,
            "claim_text": claim_text,
            "claim_date": row.get("posted"),
            "label": norm_label,
        })

    print(f"Skipped matching test IDs: {skipped_test_id}")
    print(f"Skipped matching test texts (leakage prevention): {skipped_test_text}")
    print(f"Skipped invalid labels: {skipped_invalid_label}")
    print(f"Clean non-test training pool: {len(pool)} claims")
    print(f"Pool label distribution: {Counter(r['label'] for r in pool)}")

    # 4. Stratified Split into Train (85%) and Validation (15%)
    # Use deterministic seeded shuffle by class
    import random
    rng = random.Random(42)

    by_class = {"SUPPORTED": [], "REFUTED": [], "UNVERIFIABLE": []}
    for item in pool:
        by_class[item["label"]].append(item)

    train_records = []
    val_records = []

    for cls, items in by_class.items():
        rng.shuffle(items)
        val_size = int(round(len(items) * 0.15))
        val_records.extend(items[:val_size])
        train_records.extend(items[val_size:])

    # Shuffle final train and val sets
    rng.shuffle(train_records)
    rng.shuffle(val_records)

    for item in train_records:
        item["split"] = "train"
    for item in val_records:
        item["split"] = "val"

    print("\n--- Final Dataset Splits ---")
    print(f"Train set: {len(train_records)} claims")
    print(f"  Distribution: {Counter(r['label'] for r in train_records)}")
    print(f"Validation set: {len(val_records)} claims")
    print(f"  Distribution: {Counter(r['label'] for r in val_records)}")
    print(f"Test set (held-out): {len(test_records)} claims")
    print(f"  Distribution: {Counter(r['label'] for r in test_records)}")

    # Sanity checks
    train_ids = {r["claim_id"] for r in train_records}
    val_ids = {r["claim_id"] for r in val_records}
    test_ids = {r["claim_id"] for r in test_records}

    assert len(train_ids.intersection(val_ids)) == 0, "Train and Val IDs overlap!"
    assert len(train_ids.intersection(test_ids)) == 0, "Train and Test IDs overlap!"
    assert len(val_ids.intersection(test_ids)) == 0, "Val and Test IDs overlap!"

    train_texts = {normalize_text(r["claim_text"]) for r in train_records}
    val_texts = {normalize_text(r["claim_text"]) for r in val_records}
    assert len(train_texts.intersection(test_texts_norm)) == 0, "Train texts leak into Test!"
    assert len(val_texts.intersection(test_texts_norm)) == 0, "Val texts leak into Test!"

    print("\nVerification checks PASSED: Exactly 0 leakage between train/val and test!")

    # 5. Save splits to JSON
    splits_dir = DATA_DIR / "classifier_splits"
    splits_dir.mkdir(parents=True, exist_ok=True)

    with (splits_dir / "train.json").open("w", encoding="utf-8") as f:
        json.dump(train_records, f, indent=2, ensure_ascii=False)
    with (splits_dir / "val.json").open("w", encoding="utf-8") as f:
        json.dump(val_records, f, indent=2, ensure_ascii=False)
    with (splits_dir / "test.json").open("w", encoding="utf-8") as f:
        json.dump(test_records, f, indent=2, ensure_ascii=False)

    summary = {
        "random_seed": 42,
        "total_records": len(train_records) + len(val_records) + len(test_records),
        "train_count": len(train_records),
        "val_count": len(val_records),
        "test_count": len(test_records),
        "train_distribution": dict(Counter(r["label"] for r in train_records)),
        "val_distribution": dict(Counter(r["label"] for r in val_records)),
        "test_distribution": dict(Counter(r["label"] for r in test_records)),
        "classes": ["SUPPORTED", "REFUTED", "UNVERIFIABLE"],
    }
    with (splits_dir / "split_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved split files to {splits_dir}:")
    print("  train.json")
    print("  val.json")
    print("  test.json")
    print("  split_summary.json")


if __name__ == "__main__":
    main()
