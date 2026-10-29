"""
classifier_service.py

Inference service for Model B: Pretrained MPNet Supervised Classifier.
Extracts 768-d mean-pooled sentence embeddings and evaluates them with
the calibrated multinomial classification head.

Benchmark Classes: SUPPORTED, REFUTED, UNVERIFIABLE
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from research.canonical_mapping import CLASSES

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
SPLITS_DIR = BACKEND_DIR / "data" / "classifier_splits"
CLASSIFIER_ARTIFACT_PATH = SPLITS_DIR / "model_b_mpnet_classifier.joblib"
LOCAL_SNAPSHOT_DIR = Path(
    r"C:\Users\vishn\.cache\huggingface\hub\models--sentence-transformers--all-mpnet-base-v2\snapshots\e8c3b32edf5434bc2275fc9bab85f82640a19130"
)

# Global lazy-loaded singletons for efficiency
_TOKENIZER = None
_TRANSFORMER_MODEL = None
_CLASSIFIER_HEAD = None


def get_classifier_components(
    artifact_path: Optional[Path] = None,
    snapshot_dir: Optional[Path] = None,
) -> Tuple[AutoTokenizer, AutoModel, Any]:
    """
    Lazily loads and caches the MPNet tokenizer, PyTorch Transformer model,
    and fitted scikit-learn classifier head.
    """
    global _TOKENIZER, _TRANSFORMER_MODEL, _CLASSIFIER_HEAD

    if artifact_path is None:
        artifact_path = CLASSIFIER_ARTIFACT_PATH
    if snapshot_dir is None:
        snapshot_dir = LOCAL_SNAPSHOT_DIR

    if not artifact_path.exists():
        raise FileNotFoundError(
            f"Supervised classifier artifact not found at {artifact_path}. "
            "Please ensure model_b_mpnet_classifier.joblib is present."
        )

    if not snapshot_dir.exists():
        raise FileNotFoundError(
            f"Pretrained MPNet snapshot directory not found at {snapshot_dir}."
        )

    if _TOKENIZER is None:
        logger.info("Loading MPNet tokenizer from %s", snapshot_dir)
        _TOKENIZER = AutoTokenizer.from_pretrained(snapshot_dir, local_files_only=True)

    if _TRANSFORMER_MODEL is None:
        logger.info("Loading MPNet Transformer model from %s", snapshot_dir)
        _TRANSFORMER_MODEL = AutoModel.from_pretrained(snapshot_dir, local_files_only=True)
        _TRANSFORMER_MODEL.eval()

    if _CLASSIFIER_HEAD is None:
        logger.info("Loading fitted classifier head from %s", artifact_path)
        _CLASSIFIER_HEAD = joblib.load(artifact_path)

    return _TOKENIZER, _TRANSFORMER_MODEL, _CLASSIFIER_HEAD


def extract_claim_embedding(
    text: str,
    tokenizer: AutoTokenizer,
    model: AutoModel,
    max_length: int = 128,
) -> np.ndarray:
    """
    Computes a 768-dimensional mean-pooled sentence embedding for a single text.
    """
    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("Cannot extract embedding from empty text.")

    inp = tokenizer(
        [clean_text],
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
    )

    with torch.no_grad():
        out = model(**inp)
        mask = inp["attention_mask"].unsqueeze(-1).expand(out.last_hidden_state.size()).float()
        sum_embeddings = torch.sum(out.last_hidden_state * mask, dim=1)
        sum_mask = torch.clamp(mask.sum(dim=1), min=1e-9)
        embedding = (sum_embeddings / sum_mask).cpu().numpy()

    return embedding


def classify_financial_claims(
    claims: List[Any],
    artifact_path: Optional[Path] = None,
    snapshot_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Classifies a list of claims using the pretrained MPNet + calibrated head.
    Returns structured results matching platform API conventions.
    """
    tokenizer, model, clf = get_classifier_components(artifact_path, snapshot_dir)

    results = []
    for idx, item in enumerate(claims):
        if isinstance(item, dict):
            claim_id = item.get("claim_id") or f"claim_{idx + 1}"
            claim_text = str(item.get("claim_text") or "").strip()
        else:
            claim_id = f"claim_{idx + 1}"
            claim_text = str(item).strip()

        if not claim_text:
            results.append({
                "claim_id": claim_id,
                "claim_text": claim_text,
                "status": "error",
                "error": "Claim text is empty.",
                "verdict": "ERROR",
                "confidence": None,
                "confidence_type": None,
                "probabilities": None,
                "explanation": "Cannot classify empty claim assertion.",
                "condition": "classifier",
                "model_name": "sentence-transformers/all-mpnet-base-v2 (Supervised)",
            })
            continue

        try:
            emb = extract_claim_embedding(claim_text, tokenizer, model)
            probs = clf.predict_proba(emb)[0]
            pred_idx = int(np.argmax(probs))
            verdict = CLASSES[pred_idx]
            conf = float(probs[pred_idx])

            prob_dict = {
                CLASSES[i]: round(float(probs[i]), 4) for i in range(len(CLASSES))
            }

            explanation = (
                f"Supervised MPNet Transformer representation classified assertion as {verdict} "
                f"with calibrated probability {conf * 100:.1f}%. "
                f"Class distribution: Supported={prob_dict['SUPPORTED']:.3f}, "
                f"Refuted={prob_dict['REFUTED']:.3f}, Unverifiable={prob_dict['UNVERIFIABLE']:.3f}. "
                "Prediction is based on supervised linguistic representation and does not retrieve external documents."
            )

            results.append({
                "claim_id": claim_id,
                "claim_text": claim_text,
                "status": "success",
                "verdict": verdict,
                "confidence": round(conf, 4),
                "confidence_type": "CALIBRATED_MULTINOMIAL_PROBABILITY",
                "probabilities": prob_dict,
                "explanation": explanation,
                "condition": "classifier",
                "model_name": "sentence-transformers/all-mpnet-base-v2 (Supervised)",
                "evaluator_type": "SUPERVISED_CLASSIFIER_MPNET",
                "evidence": [],
            })
        except Exception as exc:
            logger.exception("Classifier inference failed for claim %s", claim_id)
            results.append({
                "claim_id": claim_id,
                "claim_text": claim_text,
                "status": "error",
                "error": str(exc),
                "verdict": "ERROR",
                "confidence": None,
                "confidence_type": None,
                "probabilities": None,
                "explanation": f"Classifier inference failure: {exc}",
                "condition": "classifier",
                "model_name": "sentence-transformers/all-mpnet-base-v2 (Supervised)",
            })

    return results
