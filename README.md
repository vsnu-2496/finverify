# FinVerify AI · Financial News Misinformation Verification Suite

> **Research Title:** *Evidence-Grounded vs. Internal-Knowledge Verification: A Comparative Study of LLM Misinformation Detection in Financial News*  
> **Institution:** Final Year Engineering Project  
> **Repository:** `C:\Users\vishn\OneDrive\Desktop\finance-mini`

---

## 1. Overview & Research Objective

**FinVerify** is a production-grade web application and empirical benchmarking framework designed to evaluate how large language models and supervised classifiers detect financial news misinformation.

The system investigates two fundamentally distinct verification paradigms:
1. **Condition A (Internal/Parametric Knowledge):** Testing zero-shot recall of local LLMs (`Qwen2.5:3b`) without external retrieval.
2. **Condition B (Evidence-Grounded Verification):** Retrieving regulatory disclosures (SEC EDGAR Form 10-K, Form 8-K XBRL facts) and market data to ground numerical claims under strict pre-claim temporal filters.

### Key Empirical Findings (Held-Out 300 Test Claims)
- **Model A (Qwen2.5:3b Zero-Shot):** **19.00% Accuracy, 0.1186 Macro-F1**. Suffers from extreme epistemic abstention without external retrieval, predicting `UNVERIFIABLE` on 97.3% (292/300) of numerical assertions.
- **Model B (all-mpnet-base-v2 Supervised):** **57.00% Accuracy, 0.5455 Macro-F1** (**+38.00% Accuracy Gain**). Demonstrates balanced sensitivity across both true revenue claims (Supported F1: `0.6226`) and falsified figures (Refuted F1: `0.6077`).

---

## 2. Web Application Architecture & Pages

The application is built as a complete, responsive SaaS platform with zero-latency hash routing:

```
├── [Sidebar]            (Collapsible left navigation, live system indicators, model badges)
├── [Topbar]             (Sticky header, breadcrumbs, model status, Quick CTA, settings shortcut)
│
├── Page 1: Overview     (Mission, live session counters, weekly activity chart, pipeline flow, recent claims)
├── Page 2: Verify News  (2-Column workbench: Ingestion, claim segmentation, SEC grounding, live audit)
├── Page 3: History      (Session verification log, keyword search, filters, pagination, export JSON/CSV)
├── Page 4: Analytics    (Outcome ratios, segmented bar, certainty histogram, benchmark comparison)
├── Page 5: Research     (Head-to-head metrics, confusion matrices, retrieval condition status audit)
└── Page 6: Settings     (Verification defaults, source compliance, runtime diagnostics, data clearing)
```

---

## 3. Tech Stack

- **Frontend:** React 19, Vite, Tailwind CSS v4, Custom responsive SVG Data Visualizations, Space Grotesk & DM Sans typography.
- **Backend:** Python 3.14 / Flask, BeautifulSoup4, PyPDF (PdfReader), python-docx.
- **Inference Engines:**
  - Local Parametric LLM: Ollama (`qwen2.5:3b`) on `http://localhost:11434`.
  - Supervised Pretrained Transformer: `sentence-transformers/all-mpnet-base-v2` dense embeddings + Logistic Regression classifier head (`C=5.0`).
- **Grounding Sources:** SEC EDGAR XBRL Company Facts, Form 10-K, Form 8-K, Alpha Vantage Market Quotes, Curated Sample Archival Excerpts (Offline Demo Fallback).

---

## 4. API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Returns backend status and service health check |
| `POST` | `/api/news/extract` | Ingests text, URLs, or files (.pdf, .docx, .txt, .html) and parses body text |
| `POST` | `/api/news/claims` | Deterministic regex segmentation extracting numerical financial claims |
| `POST` | `/api/verify/evidence` | Condition B: Retrieves SEC filings and verifies claims against evidence |
| `POST` | `/api/verify/internal` | Condition A: Evaluates claims using local Qwen2.5:3b internal knowledge |
| `GET` | `/api/history` | Retrieves stored session verification records |
| `POST` | `/api/history` | Appends newly verified claim records to session storage |
| `PUT` | `/api/history` | Updates/replaces session history list (e.g. after item deletion) |
| `DELETE` | `/api/history` | Clears all session verification history |
| `GET` | `/api/research/results/latest` | Returns measured research metrics and Model A vs Model B comparison |
| `POST` | `/api/research/run-demo-condition-<c>` | Executes demonstration pilot run for presentation |

---

## 5. Quickstart & Installation

### Step 1: Clone or Navigate to Directory
```powershell
cd C:\Users\vishn\OneDrive\Desktop\finance-mini
```

### Step 2: Start the Local Ollama Model (Optional for Condition A)
```powershell
ollama serve
# Verify qwen2.5:3b is available:
ollama run qwen2.5:3b "Hello"
```

### Step 3: Run the Flask Backend
```powershell
cd backend
.venv\Scripts\python.exe app.py
```
*Backend runs on `http://127.0.0.1:5000`.*

### Step 4: Run the React Frontend
```powershell
cd ..\frontend
npm run dev
```
*Frontend runs on `http://localhost:5173`.*

---

## 6. Running Unit & Integration Tests

To run the backend test suite:
```powershell
cd backend
.venv\Scripts\python.exe -m unittest discover -s tests
```
*Output: 18/18 tests passing.*

To verify frontend production bundle:
```powershell
cd frontend
npm run build
```
*Output: Vite build completes with 0 errors.*
