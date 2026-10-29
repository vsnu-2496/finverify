"""Create and validate the deterministic Fin-Fact research sample."""

from collections import Counter
import json
import random
from pathlib import Path

from data.finfact_loader import (
    DEFAULT_DATASET_PATH,
    load_evaluation_records,
    load_research_records,
    validate_no_llm_leakage,
)


RANDOM_SEED = 42
TARGET_DISTRIBUTION = {"false": 133, "true": 113, "NEI": 54}
DATA_DIR = Path(__file__).resolve().parent
RESEARCH_SAMPLE_PATH = DATA_DIR / "finfact_research_sample.json"
EVALUATION_PATH = DATA_DIR / "finfact_research_evaluation.json"
METADATA_PATH = DATA_DIR / "finfact_research_sample_metadata.json"


def _select_sample(research_records, evaluation_records):
    labels_by_id = {
        record["claim_id"]: str(record["gold_label"])
        for record in evaluation_records
    }
    candidates_by_label = {label: [] for label in TARGET_DISTRIBUTION}
    for record in research_records:
        label = labels_by_id[record["claim_id"]]
        if label not in candidates_by_label:
            raise ValueError(f"Unexpected Fin-Fact label: {label}")
        candidates_by_label[label].append(record)

    selected_ids = set()
    label_offsets = {"false": 0, "true": 1, "NEI": 2}
    for label, target_count in TARGET_DISTRIBUTION.items():
        candidates = candidates_by_label[label]
        if target_count > len(candidates):
            raise ValueError(f"Not enough records for label {label}")
        selected_ids.update(
            record["claim_id"]
            for record in random.Random(RANDOM_SEED + label_offsets[label]).sample(candidates, target_count)
        )

    selected_research = [
        record for record in research_records
        if record["claim_id"] in selected_ids
    ]
    selected_evaluation = [
        record for record in evaluation_records
        if record["claim_id"] in selected_ids
    ]
    return selected_research, selected_evaluation


def validate_sample(research_records, evaluation_records, metadata):
    violations = []
    if len(research_records) != 300:
        violations.append(f"research record count is {len(research_records)}, expected 300")
    if len(evaluation_records) != 300:
        violations.append(f"evaluation record count is {len(evaluation_records)}, expected 300")

    research_ids = [record.get("claim_id") for record in research_records]
    evaluation_ids = [record.get("claim_id") for record in evaluation_records]
    if len(research_ids) != len(set(research_ids)):
        violations.append("duplicate research claim_id")
    if len(evaluation_ids) != len(set(evaluation_ids)):
        violations.append("duplicate evaluation claim_id")
    if set(research_ids) != set(evaluation_ids):
        violations.append("research/evaluation claim_id mismatch")

    research_claims = [record.get("claim_text") for record in research_records]
    if len(research_claims) != len(set(research_claims)):
        violations.append("duplicate research claim_text")

    expected_fields = {"claim_id", "claim_text", "claim_date", "author"}
    for record in research_records:
        if set(record) != expected_fields:
            violations.append(f"invalid research fields for {record.get('claim_id')}")
        try:
            validate_no_llm_leakage(record)
        except ValueError as exc:
            violations.append(str(exc))

    if any(set(record) != {"claim_id", "gold_label"} for record in evaluation_records):
        violations.append("invalid evaluation fields")
    if any(record.get("gold_label") not in TARGET_DISTRIBUTION for record in evaluation_records):
        violations.append("invalid evaluation label")

    actual_distribution = Counter(record["gold_label"] for record in evaluation_records)
    if dict(actual_distribution) != TARGET_DISTRIBUTION:
        violations.append(f"label distribution is {dict(actual_distribution)}")
    if metadata.get("actual_distribution") != TARGET_DISTRIBUTION:
        violations.append("metadata distribution mismatch")
    return violations


def prepare_sample():
    research_records = load_research_records(DEFAULT_DATASET_PATH)
    evaluation_records = load_evaluation_records(DEFAULT_DATASET_PATH)
    selected_research, selected_evaluation = _select_sample(research_records, evaluation_records)
    metadata = {
        "dataset": "Fin-Fact",
        "source_records": len(research_records),
        "sample_size": len(selected_research),
        "random_seed": RANDOM_SEED,
        "sampling_method": "stratified_random_sampling",
        "target_distribution": TARGET_DISTRIBUTION,
        "actual_distribution": dict(Counter(record["gold_label"] for record in selected_evaluation)),
        "official_split_available": False,
    }
    violations = validate_sample(selected_research, selected_evaluation, metadata)
    if violations:
        raise ValueError("Sample validation failed: " + "; ".join(violations))

    for path, payload in (
        (RESEARCH_SAMPLE_PATH, selected_research),
        (EVALUATION_PATH, selected_evaluation),
        (METADATA_PATH, metadata),
    ):
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "research_records": selected_research,
        "evaluation_records": selected_evaluation,
        "metadata": metadata,
        "violations": violations,
    }


if __name__ == "__main__":
    result = prepare_sample()
    print(json.dumps({
        "sample_size": len(result["research_records"]),
        "actual_distribution": result["metadata"]["actual_distribution"],
        "leakage_violations": len(result["violations"]),
        "research_sample": str(RESEARCH_SAMPLE_PATH),
        "evaluation": str(EVALUATION_PATH),
        "metadata": str(METADATA_PATH),
    }, indent=2))
