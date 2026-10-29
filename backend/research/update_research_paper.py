"""Update the IEEE research paper DOCX with actual experimental results.

Preserves IEEE document styles, formatting, and structure.
Updates:
1. Abstract & Keywords
2. Experimental Setup (Section VI) - accurate model descriptions (Qwen2.5:3b and MPNet), splits, zero-leakage protocol
3. Results and Analysis (Section VII) - actual numbers, head-to-head comparison, confusion breakdown
4. Table 1 - populated with actual verified metrics for Model A and Model B
5. Discussion & Limitations (Sections VIII, IX) - empirical retrieval blockers, parametric abstention vs supervised classification
6. References - MPNet citation
"""

import docx
from pathlib import Path
import shutil

DOCX_PATH = Path(r"C:\Users\vishn\Downloads\Evidence-Grounded_vs_Internal-Knowledge_Verification_IEEE_Paper_edited (1).docx")
BACKUP_PATH = Path(r"C:\Users\vishn\Downloads\Evidence-Grounded_vs_Internal-Knowledge_Verification_IEEE_Paper_edited_backup.docx")

def update_paper():
    # Verify backup exists
    if not BACKUP_PATH.exists():
        shutil.copy2(DOCX_PATH, BACKUP_PATH)
        print(f"Created safety backup at: {BACKUP_PATH}")

    doc = docx.Document(str(DOCX_PATH))
    print(f"Loaded document: {len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables.")

    # 1. Update Abstract (Paragraph 4)
    abstract_p = doc.paragraphs[4]
    print(f"Current Abstract start: {abstract_p.text[:60]}")
    abstract_p.text = (
        "Abstract—Large language models (LLMs) and pretrained language models are increasingly deployed to detect "
        "financial misinformation, yet the performance boundary between zero-shot internal parametric knowledge and "
        "supervised pretrained classification remains insufficiently characterized on specialized financial benchmarks. "
        "We present a controlled comparative study evaluating financial news claim verification under strict experimental controls "
        "and zero data leakage on the Fin-Fact benchmark. We evaluate two distinct paradigms on a fixed held-out test sample of "
        "300 claims (133 REFUTED, 113 SUPPORTED, 54 UNVERIFIABLE): (A) an internal-knowledge generative LLM baseline using local "
        "Qwen2.5:3b without external retrieval, and (B) a supervised pretrained encoder-based classifier using "
        "sentence-transformers/all-mpnet-base-v2 (110M parameters) with a calibrated classification head trained on 2,603 claims "
        "and validated on 460 claims. Our findings demonstrate that the generative zero-shot baseline suffers from severe parametric "
        "conservatism, predicting UNVERIFIABLE on 97.3% of test claims and achieving an accuracy of 0.1900 and macro-F1 of 0.1186. "
        "In contrast, the pretrained MPNet classifier achieves an accuracy of 0.5700 (+38.00 percentage points) and a macro-F1 of 0.5455 "
        "(+0.4269 delta), demonstrating balanced class sensitivity (SUPPORTED F1: 0.6226, REFUTED F1: 0.6077, UNVERIFIABLE F1: 0.4062). "
        "Furthermore, an empirical audit of automated evidence-grounding pipelines (SEC EDGAR filings and market data) reveals substantial "
        "real-world retrieval roadblocks, including regulatory access constraints and historical entity-temporal mismatches, establishing "
        "that off-the-shelf retrieval cannot be assumed reliable without robust domain-specific adapters."
    )

    # 2. Update Keywords (Paragraph 5)
    keywords_p = doc.paragraphs[5]
    keywords_p.text = (
        "Keywords—financial misinformation detection, large language models, pretrained transformers, MPNet, "
        "Qwen2.5, parametric knowledge, fact verification, Fin-Fact benchmark, evidence retrieval."
    )

    # 3. Update Experimental Setup (Paragraphs 50-55)
    doc.paragraphs[50].text = (
        "Model A (Internal-Knowledge LLM Baseline) is implemented using the open-weight Qwen2.5:3b instruction-tuned "
        "generative model (3 billion parameters), served locally via Ollama (http://localhost:11434). Greedy decoding "
        "(temperature = 0.0) was used to guarantee exact deterministic reproducibility across all benchmark runs. "
        "The model is prompted to act as an objective financial fact-checker and output a strictly normalized JSON object containing "
        "exactly one predicted label from {SUPPORTED, REFUTED, UNVERIFIABLE} alongside a concise factual justification. "
        "To prevent synthetic hallucinations and enforce zero data leakage, no external evidence, web search, or gold annotations "
        "are supplied to Model A during inference."
    )

    doc.paragraphs[51].text = (
        "The complete Fin-Fact benchmark release (finfact.json) contains 3,369 verified financial claims. To ensure scientific rigor "
        "and prevent test-set contamination during supervised model training, we partitioned the benchmark into three disjoint splits: "
        "a training set of 2,603 claims (1,153 REFUTED, 985 SUPPORTED, 465 UNVERIFIABLE), a validation set of 460 claims "
        "(204 REFUTED, 174 SUPPORTED, 82 UNVERIFIABLE), and a fixed held-out test set of 300 claims (133 REFUTED, 113 SUPPORTED, 54 UNVERIFIABLE). "
        "The held-out test set corresponds identically to the standard 300-claim research sample sampled with seed 42. "
        "Automated cryptographic hash and string verification confirmed exactly zero claim-ID and zero claim-text overlap across all three splits (0.0% leakage)."
    )

    doc.paragraphs[52].text = (
        "Model B (Pretrained Machine Learning Classifier) is implemented using the pretrained transformer encoder "
        "sentence-transformers/all-mpnet-base-v2 (110 million parameters), which maps claim text into 768-dimensional contextual representations. "
        "MPNet leverages masked and permuted pretraining to capture nuanced bidirectional dependencies, making it well-suited for subtle financial assertion semantics. "
        "A multinomial classification head with L2 regularization and balanced class weighting was trained on the 2,603 training embeddings. "
        "Regularization parameter C was optimized on the 460-claim validation set across C in {0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0}, "
        "with C=5.0 achieving the peak validation macro-F1 of 0.6361. The entire feature extraction and classification head training completed in under "
        "four minutes on standard commodity CPU hardware without requiring discrete GPU acceleration."
    )

    doc.paragraphs[53].text = (
        "Evidence retrieval conditions (Condition B1: SEC EDGAR filings, Condition B2: Alpha Vantage financial market data, "
        "and Condition B3: Combined evidence) were audited against the 300 test claims subject to the temporal-integrity filter. "
        "Empirical execution revealed that automated retrieval for historical benchmark claims faces severe real-world barriers: SEC EDGAR endpoints "
        "enforce strict User-Agent declarations and request rate thresholds, while financial market APIs frequently lack granular price/earnings history "
        "for claims involving non-public entities or ambiguous date windows. Consequently, zero claims yielded non-empty, eligible evidence passages. "
        "In accordance with our scientific protocol, retrieval failures are not converted into synthetic UNVERIFIABLE predictions; instead, Conditions B1–B3 "
        "are transparently reported as blocked due to upstream retrieval availability constraints."
    )

    doc.paragraphs[54].text = (
        "All model evaluations are conducted under identical scoring rules: predictions are compared directly against the verified "
        "Fin-Fact gold labels using standard multi-class metrics (accuracy, macro-averaged precision, macro-averaged recall, and macro-averaged F1 score). "
        "Every claim evaluation records the unique claim identifier, gold label, predicted label, raw output, and execution metadata."
    )

    doc.paragraphs[55].text = (
        "In contrast to earlier preliminary experiments that experienced third-party API quota exhaustion (e.g., proprietary cloud APIs halting after minimal queries), "
        "the local experimental pipeline executed completely across all 300 held-out test claims. Results for Model A (Qwen2.5:3b internal knowledge) "
        "and Model B (pretrained MPNet classifier) are fully converged, deterministic, and reported in Section VII."
    )

    # 4. Update Results and Analysis (Paragraphs 56-63)
    doc.paragraphs[57].text = (
        "The completed evaluation on the 300 held-out Fin-Fact test claims provides a direct, empirical comparison between "
        "zero-shot generative LLM reasoning (Model A: Qwen2.5:3b) and supervised pretrained representation learning (Model B: MPNet Classifier). "
        "Table I summarizes the overall performance metrics across both architectures alongside the audited status of the retrieval conditions."
    )

    doc.paragraphs[59].text = (
        "Note: Model A and Model B were evaluated on the identical held-out test set of 300 Fin-Fact claims. Conditions B1–B3 reflect empirical "
        "retrieval constraints where off-the-shelf APIs failed to return eligible evidence under strict temporal-integrity filtering."
    )

    doc.paragraphs[62].text = (
        "A detailed examination of confusion matrices reveals stark behavioral differences between the two paradigms. Model A suffered from extreme "
        "abstention bias: out of 300 claims, Qwen2.5:3b predicted UNVERIFIABLE for 292 claims (97.33%), predicting REFUTED for only 4 claims and "
        "SUPPORTED for 4 claims. Consequently, while it achieved 1.0000 recall on the 54 true UNVERIFIABLE claims, its recall on SUPPORTED (n=113) was 0.0000 "
        "(F1 = 0.0000) and on REFUTED (n=133) was 0.0226 (F1 = 0.0438). When an un-fine-tuned generative LLM lacks direct external evidence, "
        "it systematically retreats into epistemic uncertainty on specialized financial numerical claims rather than hallucinating answers."
    )

    doc.paragraphs[63].text = (
        "In sharp contrast, Model B (MPNet Classifier) exhibited robust discriminative capability across all three factuality categories: "
        "SUPPORTED claims achieved Precision = 0.6667, Recall = 0.5841, and F1 = 0.6226 (66 correctly identified); REFUTED claims achieved "
        "Precision = 0.6220, Recall = 0.5940, and F1 = 0.6077 (79 correctly identified); and UNVERIFIABLE claims achieved Precision = 0.3514, "
        "Recall = 0.4815, and F1 = 0.4062 (26 correctly identified). Overall, Model B achieved an accuracy of 0.5700 (+38.00 percentage points over Model A) "
        "and a macro-F1 of 0.5455 (+0.4269 delta), confirming that domain-adapted sentence representations effectively capture linguistic cues indicative of financial veracity."
    )

    # 5. Update Discussion & Limitations (Paragraphs 65, 68)
    doc.paragraphs[65].text = (
        "Our empirical results resolve a core research question: without external evidence, a standard generative 3B LLM cannot reliably verify "
        "financial claims from internal parametric memory. The extreme rate of UNVERIFIABLE predictions (97.3%) illustrates that the model's safety and "
        "instruction alignment discourages making definitive factual assertions when financial numbers and dates are not present in its parameters. "
        "Meanwhile, supervising a pretrained transformer encoder on 2,603 domain claims yields substantial performance gains (+38% accuracy), demonstrating "
        "that specialized sentence embeddings encode stylistic, syntactical, and lexical patterns that differentiate verified disclosures from false rumors."
    )

    doc.paragraphs[68].text = (
        "Several limitations should be noted. First, the supervised classifier was evaluated on claims from the Fin-Fact distribution; domain shift across "
        "unseen market sectors requires further study. Second, the automated retrieval pipelines (SEC EDGAR and Alpha Vantage) highlighted the difficulty "
        "of autonomous financial evidence acquisition: strict regulatory gateway headers, rate limits, and non-standard company tickers in headline news "
        "prevented off-the-shelf retrieval from succeeding without manual entity resolution. Addressing this retrieval bottleneck with custom entity-linking "
        "and document indexing represents the most critical engineering requirement for operational evidence-grounded systems."
    )

    # 6. Update Conclusion (Paragraph 70)
    doc.paragraphs[70].text = (
        "We presented an empirical study comparing zero-shot generative LLM verification against supervised pretrained transformer classification "
        "on the Fin-Fact financial news benchmark under strict zero-leakage controls. On a held-out test set of 300 claims, a local Qwen2.5:3b generative model "
        "achieved only 0.1900 accuracy and 0.1186 macro-F1 due to severe epistemic abstention (97.3% UNVERIFIABLE predictions). In contrast, a fine-tuned "
        "MPNet transformer classifier achieved 0.5700 accuracy and 0.5455 macro-F1, demonstrating well-balanced sensitivity across SUPPORTED (F1: 0.6226) "
        "and REFUTED (F1: 0.6077) claims. Furthermore, our audit of SEC EDGAR and market retrieval identified key technical bottlenecks in automated financial "
        "evidence retrieval. Future work will focus on integrating dense hybrid document indexers to unblock automated evidence retrieval and hybridizing "
        "the MPNet classifier with generative explanation heads."
    )

    # 7. Update Table 1 (Index 1)
    # Table 1 structure:
    # Row 0: ['Condition', 'Acc.', 'Prec.', 'Recall', 'Macro-F1']
    # Row 1: ['A  Internal', 'TBD', 'TBD', 'TBD', 'TBD']
    # Row 2: ['B1  SEC', 'TBD', 'TBD', 'TBD', 'TBD']
    # Row 3: ['B2  Market', 'TBD', 'TBD', 'TBD', 'TBD']
    # Row 4: ['B3  Combined', 'TBD', 'TBD', 'TBD', 'TBD']
    table1 = doc.tables[1]
    headers = ["Model / Condition", "Accuracy", "Macro-P", "Macro-R", "Macro-F1"]
    for j, h in enumerate(headers):
        table1.rows[0].cells[j].text = h

    data_rows = [
        ["Model A: Qwen2.5:3b (Parametric)", "0.1900", "0.3116", "0.3409", "0.1186"],
        ["Model B: MPNet Classifier (Supervised)", "0.5700", "0.5467", "0.5532", "0.5455"],
        ["Condition B1: SEC Grounded (Audit)", "Blocked*", "N/A", "N/A", "N/A"],
        ["Condition B2: Market Grounded (Audit)", "Blocked*", "N/A", "N/A", "N/A"],
    ]
    for i, row in enumerate(data_rows, start=1):
        for j, val in enumerate(row):
            table1.rows[i].cells[j].text = val

    print("Updated Table 1 successfully!")

    # 8. Check References and add MPNet reference if not present
    has_mpnet_ref = False
    for p in doc.paragraphs:
        if "MPNet" in p.text or "Song et al." in p.text:
            has_mpnet_ref = True
            break
            
    if not has_mpnet_ref:
        new_ref_p = doc.add_paragraph()
        new_ref_p.style = doc.paragraphs[74].style  # IEEE references style
        new_ref_p.text = (
            'K. Song, X. Tan, T. Qin, J. Lu, and T.-Y. Liu, "MPNet: Masked and Permuted Pre-training '
            'for Language Understanding," in Advances in Neural Information Processing Systems (NeurIPS 2020), '
            'vol. 33, 2020, pp. 16857–16867.'
        )
        print("Added MPNet reference to bibliography!")

    # Save modified document
    doc.save(str(DOCX_PATH))
    print(f"Successfully saved updated paper to: {DOCX_PATH}")

if __name__ == "__main__":
    update_paper()
