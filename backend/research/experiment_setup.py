"""Deterministic, leakage-safe preparation for the Fin-Fact pilot experiment."""

from datetime import date
import random

from data.finfact_loader import (
    DEFAULT_DATASET_PATH,
    inspect_dataset,
    load_evaluation_records,
    load_research_records,
)
from research.config import (
    CLASSES,
    CONDITIONS,
    DATASET_NAME,
    EXPERIMENT_NAME,
    LABEL_MAPPING,
    PILOT_SAMPLE_SIZE,
    RANDOM_SEED,
    SAMPLE_SIZE_PER_CLASS,
)

SAFE_LLM_FIELDS = ("claim_id", "claim_text", "claim_date")


def _normalized_gold_label(raw_label):
    try:
        return LABEL_MAPPING[str(raw_label)]
    except KeyError as exc:
        raise ValueError(f"Unexpected Fin-Fact label: {raw_label!r}") from exc


def _valid_iso_date(value):
    if not value:
        return None
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return value


def _evaluation_records():
    """Return pilot records using the canonical Fin-Fact research claim_date.

    This `claim_date` is the benchmark's posted/publication date normalized to ISO
    format; it is not inferred from the claim text and does not model reporting
    periods separately.
    """
    research_records = load_research_records(DEFAULT_DATASET_PATH)
    eval_records = load_evaluation_records(DEFAULT_DATASET_PATH)
    eval_by_id = {item["claim_id"]: item["gold_label"] for item in eval_records}

    records = []
    for record in research_records:
        gold = eval_by_id.get(record["claim_id"])
        if gold is None:
            continue
        records.append({
            "claim_id": record["claim_id"],
            "claim_text": record["claim_text"],
            "claim_date": _valid_iso_date(record.get("claim_date")),
            "gold_label": _normalized_gold_label(gold),
            "split": "research",
        })
    return records


def get_pilot_evaluation_records():
    """Select the same 25 records per mapped class on every invocation."""
    records_by_class = {label: [] for label in CLASSES}
    for record in _evaluation_records():
        records_by_class[record["gold_label"]].append(record)

    selected = []
    for class_name in CLASSES:
        candidates = list(records_by_class[class_name])
        random.Random(RANDOM_SEED).shuffle(candidates)
        if len(candidates) < SAMPLE_SIZE_PER_CLASS:
            raise ValueError(f"Not enough records for class {class_name}.")
        selected.extend(candidates[:SAMPLE_SIZE_PER_CLASS])

    return selected


def get_pilot_llm_inputs():
    """Return only fields permitted in either condition's claim input."""
    return [
        {field: record[field] for field in SAFE_LLM_FIELDS}
        for record in get_pilot_evaluation_records()
    ]


def get_experiment_metadata():
    evaluation_records = get_pilot_evaluation_records()
    class_counts = {class_name: 0 for class_name in CLASSES}
    for record in evaluation_records:
        class_counts[record["gold_label"]] += 1

    valid_dates = sum(record["claim_date"] is not None for record in evaluation_records)
    return {
        "experiment_name": EXPERIMENT_NAME,
        "dataset": DATASET_NAME,
        "random_seed": RANDOM_SEED,
        "total_dataset_records": inspect_dataset(DEFAULT_DATASET_PATH)["total_records"],
        "pilot_sample_size": PILOT_SAMPLE_SIZE,
        "class_counts": class_counts,
        "valid_claim_dates": valid_dates,
        "missing_claim_dates": PILOT_SAMPLE_SIZE - valid_dates,
        "conditions": list(CONDITIONS),
        "llm_experiment_executed": False,
    }


def get_pilot_preview(limit=5):
    return get_pilot_llm_inputs()[:limit]
