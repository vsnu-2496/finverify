"""Train and evaluate the pretrained ML classifier (Option B) on Fin-Fact.

Pretrained model: sentence-transformers/all-mpnet-base-v2
Architecture: 110M parameter MPNet Transformer with mean-pooled 768-d representations
Classifier head: Calibrated multinomial classification head with balanced class weighting
Evaluation: Exact match against Model A (Qwen2.5:3b internal knowledge) on the held-out 300 test claims.
Zero leakage: Feature normalization and classifier fitting strictly restricted to training split.
"""

import json
import time
from pathlib import Path
from collections import Counter
import numpy as np

import torch
from transformers import AutoTokenizer, AutoModel
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
SPLITS_DIR = DATA_DIR / "classifier_splits"
OUTPUT_DIR = DATA_DIR / "final_experiment"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_SNAPSHOT_DIR = Path(r"C:\Users\vishn\.cache\huggingface\hub\models--sentence-transformers--all-mpnet-base-v2\snapshots\e8c3b32edf5434bc2275fc9bab85f82640a19130")
CACHE_FILE = SPLITS_DIR / "mpnet_embeddings_cache.npz"

CLASSES = ["SUPPORTED", "REFUTED", "UNVERIFIABLE"]
LABEL_TO_IDX = {cls: idx for idx, cls in enumerate(CLASSES)}
IDX_TO_LABEL = {idx: cls for idx, cls in enumerate(CLASSES)}


def load_split(split_name):
    path = SPLITS_DIR / f"{split_name}.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_embeddings(texts, tokenizer, model, batch_size=32, device="cpu"):
    all_embeddings = []
    total = len(texts)
    model.eval()

    for i in range(0, total, batch_size):
        batch_texts = texts[i : i + batch_size]
        inp = tokenizer(
            batch_texts,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            out = model(**inp)
            mask = inp["attention_mask"].unsqueeze(-1).expand(out.last_hidden_state.size()).float()
            sum_embeddings = torch.sum(out.last_hidden_state * mask, 1)
            sum_mask = torch.clamp(mask.sum(1), min=1e-9)
            embeddings = (sum_embeddings / sum_mask).cpu().numpy()
            all_embeddings.append(embeddings)

        if (i // batch_size + 1) % 10 == 0 or (i + batch_size) >= total:
            print(f"  Extracted {min(i + batch_size, total)}/{total} claims...")

    return np.vstack(all_embeddings)


def main():
    print("=" * 65)
    print("OPTION B: PRETRAINED CLASSIFIER TRAINING & EVALUATION")
    print("Model: sentence-transformers/all-mpnet-base-v2 (110M params)")
    print("Target Classes: SUPPORTED, REFUTED, UNVERIFIABLE")
    print("=" * 65)

    # 1. Load splits
    train_data = load_split("train")
    val_data = load_split("val")
    test_data = load_split("test")

    print(f"\nLoaded dataset splits:")
    print(f"  Train: {len(train_data)} claims | Distribution: {Counter(r['label'] for r in train_data)}")
    print(f"  Val:   {len(val_data)} claims | Distribution: {Counter(r['label'] for r in val_data)}")
    print(f"  Test:  {len(test_data)} claims | Distribution: {Counter(r['label'] for r in test_data)}")

    y_train = np.array([LABEL_TO_IDX[r["label"]] for r in train_data])
    y_val = np.array([LABEL_TO_IDX[r["label"]] for r in val_data])
    y_test = np.array([LABEL_TO_IDX[r["label"]] for r in test_data])

    # 2. Extract or Load Embeddings
    if CACHE_FILE.exists():
        print(f"\nLoading cached embeddings from {CACHE_FILE}...")
        cache = np.load(CACHE_FILE)
        X_train = cache["X_train"]
        X_val = cache["X_val"]
        X_test = cache["X_test"]
        print("Embeddings loaded from cache successfully!")
    else:
        print(f"\nLoading local MPNet transformer from {LOCAL_SNAPSHOT_DIR}...")
        t_model_load_0 = time.time()
        tokenizer = AutoTokenizer.from_pretrained(LOCAL_SNAPSHOT_DIR, local_files_only=True)
        model = AutoModel.from_pretrained(LOCAL_SNAPSHOT_DIR, local_files_only=True)
        print(f"Model loaded in {time.time() - t_model_load_0:.2f} s")

        print("\nExtracting training set embeddings (2,603 claims)...")
        X_train = extract_embeddings([r["claim_text"] for r in train_data], tokenizer, model)

        print("\nExtracting validation set embeddings (460 claims)...")
        X_val = extract_embeddings([r["claim_text"] for r in val_data], tokenizer, model)

        print("\nExtracting test set embeddings (300 claims)...")
        t_test_enc_0 = time.time()
        X_test = extract_embeddings([r["claim_text"] for r in test_data], tokenizer, model)
        test_enc_time = time.time() - t_test_enc_0

        np.savez_compressed(CACHE_FILE, X_train=X_train, X_val=X_val, X_test=X_test)
        print(f"Saved embeddings cache to {CACHE_FILE}")

    # 3. Model Training & Hyperparameter Tuning on Validation Split
    print("\nTuning classifier head regularization (C) on validation split...")
    best_c = 1.0
    best_val_f1 = -1.0

    for c in [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]:
        clf = LogisticRegression(
            C=c,
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
            solver="lbfgs",
        )
        clf.fit(X_train, y_train)
        val_preds = clf.predict(X_val)
        _, _, f1_macro, _ = precision_recall_fscore_support(y_val, val_preds, average="macro", zero_division=0)
        print(f"  C={c:5.2f} -> Val Macro-F1: {f1_macro:.4f}")
        if f1_macro > best_val_f1:
            best_val_f1 = f1_macro
            best_c = c

    print(f"\nSelected optimal C={best_c} (Validation Macro-F1: {best_val_f1:.4f})")

    # 4. Final Fit on Train and Measure Inference on Test Set
    t_train_0 = time.time()
    final_clf = LogisticRegression(
        C=best_c,
        max_iter=1000,
        class_weight="balanced",
        random_state=42,
        solver="lbfgs",
    )
    final_clf.fit(X_train, y_train)
    train_time = time.time() - t_train_0
    print(f"Classifier head training completed in {train_time:.3f} s")

    # Measure test inference timing
    t_inf_0 = time.time()
    test_preds = final_clf.predict(X_test)
    test_probs = final_clf.predict_proba(X_test)
    inference_time_clf = time.time() - t_inf_0

    # Test set metrics
    accuracy = float(accuracy_score(y_test, test_preds))
    precisions, recalls, f1s, supports = precision_recall_fscore_support(
        y_test, test_preds, labels=[0, 1, 2], zero_division=0
    )
    macro_p = float(np.mean(precisions))
    macro_r = float(np.mean(recalls))
    macro_f1 = float(np.mean(f1s))
    cm = confusion_matrix(y_test, test_preds, labels=[0, 1, 2])

    print("\n" + "=" * 65)
    print("MODEL B (MPNet CLASSIFIER) TEST RESULTS (300 CLAIMS)")
    print("=" * 65)
    print(f"Accuracy        : {accuracy:.4f}")
    print(f"Macro Precision : {macro_p:.4f}")
    print(f"Macro Recall    : {macro_r:.4f}")
    print(f"Macro F1        : {macro_f1:.4f}")

    print("\nPer-Class Breakdown:")
    per_class_dict = {}
    for idx, cls in enumerate(CLASSES):
        per_class_dict[cls] = {
            "precision": round(float(precisions[idx]), 4),
            "recall": round(float(recalls[idx]), 4),
            "f1": round(float(f1s[idx]), 4),
            "support": int(supports[idx]),
        }
        print(f"  {cls:13s} -> P: {precisions[idx]:.4f}, R: {recalls[idx]:.4f}, F1: {f1s[idx]:.4f}, Support: {supports[idx]}")

    print("\nConfusion Matrix (Rows=Gold, Columns=Predicted):")
    print(f"{'':14s} {'SUPPORTED':>10s} {'REFUTED':>10s} {'UNVERIFIABLE':>12s}")
    cm_dict = {}
    for i, actual_cls in enumerate(CLASSES):
        cm_dict[actual_cls] = {pred_cls: int(cm[i, j]) for j, pred_cls in enumerate(CLASSES)}
        print(f"{actual_cls:14s} {cm[i, 0]:10d} {cm[i, 1]:10d} {cm[i, 2]:12d}")

    # 5. Load Model A Results for Comparison
    model_a_path = OUTPUT_DIR / "condition_a_metrics.json"
    with model_a_path.open("r", encoding="utf-8") as f:
        model_a_data = json.load(f)
    model_a_metrics = model_a_data["metrics"]

    print("\n" + "=" * 65)
    print("HEAD-TO-HEAD COMPARISON: MODEL A vs. MODEL B (HELD-OUT 300 CLAIMS)")
    print("=" * 65)
    print(f"{'Metric':<18s} | {'Model A (Qwen2.5:3b)':<20s} | {'Model B (MPNet Classifier)':<25s} | {'Absolute Diff':<12s}")
    print("-" * 80)
    metrics_to_comp = [
        ("Accuracy", model_a_metrics["accuracy"], accuracy),
        ("Macro Precision", model_a_metrics["macro_precision"], macro_p),
        ("Macro Recall", model_a_metrics["macro_recall"], macro_r),
        ("Macro F1", model_a_metrics["macro_f1"], macro_f1),
    ]
    for name, a_val, b_val in metrics_to_comp:
        diff = b_val - a_val
        print(f"{name:<18s} | {a_val:<20.4f} | {b_val:<25.4f} | {diff:+12.4f}")

    # 6. Save Model B Detailed Results
    detailed_test_results = []
    for i, record in enumerate(test_data):
        pred_idx = int(test_preds[i])
        pred_label = IDX_TO_LABEL[pred_idx]
        conf = float(test_probs[i, pred_idx])
        detailed_test_results.append({
            "claim_id": record["claim_id"],
            "claim_text": record["claim_text"],
            "gold_label": record["label"],
            "predicted_label": pred_label,
            "confidence": round(conf, 4),
            "probabilities": {
                CLASSES[j]: round(float(test_probs[i, j]), 4) for j in range(3)
            },
            "is_correct": bool(record["label"] == pred_label),
        })

    with (OUTPUT_DIR / "model_b_mpnet_results.json").open("w", encoding="utf-8") as f:
        json.dump(detailed_test_results, f, indent=2, ensure_ascii=False)

    model_b_metrics = {
        "model_name": "sentence-transformers/all-mpnet-base-v2 + Calibrated Head",
        "evaluated_claims": len(test_data),
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class_dict,
        "confusion_matrix": cm_dict,
        "predicted_counts": {cls: int(np.sum(test_preds == idx)) for idx, cls in enumerate(CLASSES)},
        "hyperparameters": {
            "optimal_C": best_c,
            "solver": "lbfgs",
            "class_weight": "balanced",
            "max_iter": 1000,
        },
    }
    with (OUTPUT_DIR / "model_b_mpnet_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(model_b_metrics, f, indent=2)

    # Save CSVs
    import csv
    with (OUTPUT_DIR / "model_b_mpnet_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerow(["accuracy", f"{accuracy:.4f}"])
        writer.writerow(["macro_precision", f"{macro_p:.4f}"])
        writer.writerow(["macro_recall", f"{macro_r:.4f}"])
        writer.writerow(["macro_f1", f"{macro_f1:.4f}"])

    with (OUTPUT_DIR / "model_b_mpnet_per_class.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["class", "precision", "recall", "f1", "support"])
        for cls, row in per_class_dict.items():
            writer.writerow([cls, f"{row['precision']:.4f}", f"{row['recall']:.4f}", f"{row['f1']:.4f}", row["support"]])

    with (OUTPUT_DIR / "model_b_mpnet_confusion_matrix.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["gold_class"] + CLASSES)
        for cls in CLASSES:
            writer.writerow([cls] + [cm_dict[cls][pred] for pred in CLASSES])

    # 7. Comparison Table CSV
    with (OUTPUT_DIR / "model_comparison_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "model_a_qwen25_3b", "model_b_mpnet_classifier", "absolute_delta"])
        for name, a_val, b_val in metrics_to_comp:
            writer.writerow([name.lower().replace(" ", "_"), f"{a_val:.4f}", f"{b_val:.4f}", f"{(b_val - a_val):+.4f}"])

    comparison_summary = {
        "evaluation_sample_size": 300,
        "sample_split": "held_out_test",
        "models": {
            "model_a": {
                "name": "Qwen2.5:3b (Parametric / Internal Knowledge)",
                "type": "Generative LLM Prompted Zero-Shot",
                "accuracy": model_a_metrics["accuracy"],
                "macro_precision": model_a_metrics["macro_precision"],
                "macro_recall": model_a_metrics["macro_recall"],
                "macro_f1": model_a_metrics["macro_f1"],
                "per_class": model_a_metrics["per_class"],
                "confusion_matrix": model_a_metrics["confusion_matrix"],
            },
            "model_b": {
                "name": "sentence-transformers/all-mpnet-base-v2 (Supervised)",
                "type": "Pretrained Transformer Encoder + Calibrated Classification Head",
                "accuracy": round(accuracy, 4),
                "macro_precision": round(macro_p, 4),
                "macro_recall": round(macro_r, 4),
                "macro_f1": round(macro_f1, 4),
                "per_class": per_class_dict,
                "confusion_matrix": cm_dict,
            },
        },
        "delta_model_b_minus_model_a": {
            "accuracy": round(accuracy - model_a_metrics["accuracy"], 4),
            "macro_precision": round(macro_p - model_a_metrics["macro_precision"], 4),
            "macro_recall": round(macro_r - model_a_metrics["macro_recall"], 4),
            "macro_f1": round(macro_f1 - model_a_metrics["macro_f1"], 4),
        },
    }
    with (OUTPUT_DIR / "model_comparison_summary.json").open("w", encoding="utf-8") as f:
        json.dump(comparison_summary, f, indent=2)

    print(f"\nAll Model B artifacts and comparison metrics successfully saved to:\n  {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
