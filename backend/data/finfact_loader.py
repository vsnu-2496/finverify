"""Safe inspection and research-input preparation for the Fin-Fact benchmark."""

from collections import Counter
from datetime import datetime
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = PROJECT_ROOT / "finfact.json"

LEAKAGE_FIELDS = {
    "label",
    "evidence",
    "hrefs",
    "justification",
    "issues",
    "image_data",
    "visualization_bias",
    "sci_digest",
    "url",
}


def _is_missing(value):
    return value is None or value == "" or value == []


def _normalize_date(value):
    if _is_missing(value):
        return None
    text = str(value).strip()
    for date_format in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _load_rows(dataset_path=DEFAULT_DATASET_PATH):
    with dataset_path.open("r", encoding="utf-8") as dataset_file:
        payload = json.load(dataset_file)
    if not isinstance(payload, list):
        raise ValueError("Fin-Fact JSON must contain a top-level array of records.")
    if not all(isinstance(row, dict) for row in payload):
        raise ValueError("Every Fin-Fact record must be a JSON object.")
    return payload


def inspect_dataset(dataset_path=DEFAULT_DATASET_PATH):
    dataset_path = Path(dataset_path)
    if not dataset_path.is_file():
        return {
            "dataset_found": False,
            "dataset_path": str(dataset_path),
            "total_records": 0,
            "available_fields": [],
            "claim_field": None,
            "label_field": None,
            "date_field": None,
            "split_field": None,
            "label_distribution": {},
            "missing_value_summary": {},
            "duplicate_claim_count": 0,
            "leakage_fields": [],
            "prepared_records_count": 0,
        }

    rows = _load_rows(dataset_path)
    fields = list(dict.fromkeys(field for row in rows for field in row))
    claim_field = "claim"
    label_field = "label"
    date_field = "posted"
    split_field = None

    label_distribution = Counter()
    if label_field:
        label_distribution.update(str(row[label_field]) for row in rows if not _is_missing(row.get(label_field)))

    missing_value_summary = {
        field: sum(1 for row in rows if field not in row or _is_missing(row.get(field)))
        for field in fields
    }

    duplicate_claim_count = 0
    if claim_field:
        claim_counts = Counter(row.get(claim_field) for row in rows)
        duplicate_claim_count = sum(count - 1 for count in claim_counts.values() if count > 1)

    leakage_fields = [field for field in fields if field.lower() in LEAKAGE_FIELDS]
    if any(isinstance(row.get("evidence"), list) and any("hrefs" in item for item in row["evidence"] if isinstance(item, dict)) for row in rows):
        leakage_fields.append("evidence[*].hrefs")

    return {
        "dataset_found": True,
        "dataset_path": str(dataset_path),
        "total_records": len(rows),
        "available_fields": fields,
        "claim_field": claim_field,
        "label_field": label_field,
        "date_field": date_field,
        "split_field": split_field,
        "label_distribution": dict(label_distribution),
        "missing_value_summary": missing_value_summary,
        "duplicate_claim_count": duplicate_claim_count,
        "leakage_fields": list(dict.fromkeys(leakage_fields)),
        "prepared_records_count": len(rows) if claim_field else 0,
    }


def get_canonical_research_claim_date(raw_posted):
    """Return the canonical temporal cutoff for the controlled Fin-Fact experiment.

    The research benchmark uses the original Fin-Fact `posted` field, normalized to
    ISO format YYYY-MM-DD. This is the fixed benchmark date used for the controlled
    experiment and is not a reporting-period or economic-date annotation.
    """
    return _normalize_date(raw_posted)


def load_research_records(dataset_path=DEFAULT_DATASET_PATH):
    """Return only safe LLM inputs in the original dataset order.

    `claim_date` is the canonical research cutoff date: the Fin-Fact `posted` value,
    normalized to ISO format. The experiment does not separately model reporting
    periods or claim-specific start/end dates.
    """
    rows = _load_rows(dataset_path)
    records = []
    for index, row in enumerate(rows, start=1):
        records.append({
            "claim_id": f"finfact_{index:06d}",
            "claim_text": str(row.get("claim", "")),
            "claim_date": get_canonical_research_claim_date(row.get("posted")),
            "author": str(row.get("author", "")),
        })
    return records


def load_evaluation_records(dataset_path=DEFAULT_DATASET_PATH):
    """Return gold labels separately from the records supplied to an LLM."""
    rows = _load_rows(dataset_path)
    return [
        {
            "claim_id": f"finfact_{index:06d}",
            "gold_label": row.get("label"),
        }
        for index, row in enumerate(rows, start=1)
    ]


def validate_no_llm_leakage(record):
    """Raise ValueError if a prepared LLM input contains benchmark fields."""
    if not isinstance(record, dict):
        raise ValueError("LLM input must be a dictionary.")

    present = set(record)
    violations = sorted(field for field in present if field.lower() in LEAKAGE_FIELDS)
    nested_hrefs = any(
        isinstance(value, dict) and "hrefs" in value
        for value in record.values()
    )
    if nested_hrefs:
        violations.append("hrefs")
    if violations:
        raise ValueError(f"LLM leakage fields present: {sorted(set(violations))}")
    return True


def get_safe_preview(dataset_path=DEFAULT_DATASET_PATH, limit=5):
    """Return only fields permitted as research inputs, excluding all gold data."""
    records = load_research_records(dataset_path)[:limit]
    for record in records:
        validate_no_llm_leakage(record)
    return records
