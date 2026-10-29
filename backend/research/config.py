"""Immutable controls for the Fin-Fact comparative research setup."""

EXPERIMENT_NAME = "evidence_grounded_vs_internal_knowledge"
DATASET_NAME = "finfact.json"
RANDOM_SEED = 42
PILOT_SAMPLE_SIZE = 75
SAMPLE_SIZE_PER_CLASS = 25

LABEL_MAPPING = {
    "true": "SUPPORTED",
    "false": "REFUTED",
    "NEI": "UNVERIFIABLE",
}
CLASSES = ("SUPPORTED", "REFUTED", "UNVERIFIABLE")
CONDITIONS = ("A_INTERNAL_KNOWLEDGE", "B_EVIDENCE_GROUNDED")

SAME_CLAIMS_ACROSS_CONDITIONS = True
SAME_LLM_ACROSS_CONDITIONS = True
SAME_PROMPT_STRUCTURE = True
GOLD_LABEL_IN_LLM_INPUT = False
FINFACT_EVIDENCE_IN_LLM_INPUT = False
FINFACT_JUSTIFICATION_IN_LLM_INPUT = False

# Condition B retrieval is intentionally described here but not executed by setup.
CONDITION_INPUTS = {
    "A_INTERNAL_KNOWLEDGE": ("claim_text", "claim_date"),
    "B_EVIDENCE_GROUNDED": ("claim_text", "claim_date", "external_evidence"),
}
APPROVED_EXTERNAL_SOURCES = ("SEC EDGAR", "Alpha Vantage")
