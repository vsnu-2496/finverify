import React, { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:5000';

const PRESET_SAMPLES = [
  {
    id: 'aapl-true',
    company: 'Apple Inc.',
    label: 'Apple FY23 Net Sales ($383.29B)',
    truth: 'SUPPORTED',
    truthBadge: 'Gold: True',
    text: 'Apple Inc. announced its financial results for fiscal year 2023. Apple reported total net sales of $383,285 million ($383.29 billion) for fiscal year 2023, compared to $394,328 million in 2022.',
    summary: 'Audited 10-K reported net sales of $383,285M.',
  },
  {
    id: 'aapl-fake',
    company: 'Apple Inc.',
    label: 'Apple Fake Revenue ($950B)',
    truth: 'REFUTED',
    truthBadge: 'Gold: False',
    text: 'Financial headlines falsely claimed that Apple reported total net sales of $950 billion for fiscal year 2023, representing record revenue growth.',
    summary: 'Directly contradicts the official 10-K filing ($383.29B).',
  },
  {
    id: 'msft-buyout',
    company: 'Microsoft Corp.',
    label: 'Microsoft Activision Buyout ($68.7B)',
    truth: 'SUPPORTED',
    truthBadge: 'Gold: True',
    text: 'Microsoft Corporation filed Form 8-K stating that it completed the acquisition of Activision Blizzard for approximately $68.7 billion in October 2023.',
    summary: 'Confirmed by official Form 8-K corporate acquisition filing.',
  },
  {
    id: 'pfe-revenue',
    company: 'Pfizer Inc.',
    label: 'Pfizer FY22 Revenue ($100.3B)',
    truth: 'SUPPORTED',
    truthBadge: 'Gold: True',
    text: 'Pfizer Inc. reported total revenues of $100.3 billion ($100,330 million) for the year ended December 31, 2022, driven by vaccine sales.',
    summary: 'Confirmed by Pfizer Form 10-K filing.',
  },
];

export default function VerifyNewsPage({ onVerificationComplete, initialClaimText }) {
  // Input states
  const [inputTab, setInputTab] = useState('text'); // 'text' | 'url' | 'file'
  const [articleText, setArticleText] = useState(initialClaimText || PRESET_SAMPLES[0].text);
  const [articleUrl, setArticleUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);

  // Sync if initialClaimText is passed later
  React.useEffect(() => {
    if (initialClaimText) {
      setInputTab('text');
      setArticleText(initialClaimText);
      const generated = [{ claim_id: 'CLM-01', claim_text: initialClaimText }];
      setClaims(generated);
      setSelectedClaimIds(new Set(['CLM-01']));
      setResults([]);
    }
  }, [initialClaimText]);

  // Extraction & Verification states
  const [extracting, setExtracting] = useState(false);
  const [extractedArticle, setExtractedArticle] = useState(null);
  const [claims, setClaims] = useState([
    {
      claim_id: 'CLM-01',
      claim_text: initialClaimText || 'Apple reported total net sales of $383,285 million ($383.29 billion) for fiscal year 2023, compared to $394,328 million in 2022.',
    },
  ]);
  const [selectedClaimIds, setSelectedClaimIds] = useState(new Set(['CLM-01']));
  const [extractingClaims, setExtractingClaims] = useState(false);

  // Verification process
  const [activeCondition, setActiveCondition] = useState('evidence'); // 'internal' | 'evidence' | 'classifier'
  const [useSampleFallback, setUseSampleFallback] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [results, setResults] = useState([]);
  const [errorMsg, setErrorMsg] = useState('');
  const [isOfflineService, setIsOfflineService] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState({});

  // 1. Ingestion: Extract Article Text
  const handleExtractArticle = async (e) => {
    if (e) e.preventDefault();
    setErrorMsg('');
    setExtracting(true);
    setExtractedArticle(null);
    setClaims([]);
    setSelectedClaimIds(new Set());
    setResults([]);

    try {
      if (inputTab === 'text' && !articleText.trim()) {
        throw new Error('Please enter financial news text or pick a quick sample.');
      }
      if (inputTab === 'url' && !articleUrl.trim()) {
        throw new Error('Please enter a valid financial news article URL.');
      }
      if (inputTab === 'file' && !selectedFile) {
        throw new Error('Please select a document file (.pdf, .docx, .txt, .html).');
      }

      const formData = new FormData();
      if (inputTab === 'file') formData.append('file', selectedFile);
      if (inputTab === 'text') formData.append('articleText', articleText);
      if (inputTab === 'url') formData.append('url', articleUrl);

      const resp = await axios.post(`${API_BASE_URL}/api/news/extract`, formData);
      setExtractedArticle(resp.data);

      // Split into claims
      await splitArticleIntoClaims(resp.data.article_text);
    } catch (err) {
      setErrorMsg(err.response?.data?.article_text || err.message || 'Article extraction failed.');
    } finally {
      setExtracting(false);
    }
  };

  // 2. Claim Segmentation
  const splitArticleIntoClaims = async (rawText) => {
    setExtractingClaims(true);
    try {
      const resp = await axios.post(`${API_BASE_URL}/api/news/claims`, { article_text: rawText });
      const extracted = resp.data.claims || [];
      setClaims(extracted);
      setSelectedClaimIds(new Set(extracted.map((c) => c.claim_id)));
    } catch (err) {
      // If segmentation endpoint fails, fallback to simple sentence segmentation
      const sentences = rawText
        .split(/(?<=[.!?])\s+/)
        .filter((s) => s.length > 20 && /\d/.test(s))
        .slice(0, 5)
        .map((s, idx) => ({ claim_id: `CLM-0${idx + 1}`, claim_text: s }));
      setClaims(sentences);
      setSelectedClaimIds(new Set(sentences.map((c) => c.claim_id)));
    } finally {
      setExtractingClaims(false);
    }
  };

  // Toggle individual claim selection
  const toggleClaim = (claimId) => {
    const next = new Set(selectedClaimIds);
    if (next.has(claimId)) next.delete(claimId);
    else next.add(claimId);
    setSelectedClaimIds(next);
  };

  const selectAllClaims = () => {
    setSelectedClaimIds(new Set(claims.map((c) => c.claim_id)));
  };

  const deselectAllClaims = () => {
    setSelectedClaimIds(new Set());
  };

  // 3. Verification Execution
  const handleVerify = async (condition) => {
    const targetCondition = condition || activeCondition;
    setErrorMsg('');
    setIsOfflineService(false);
    const targetClaims = claims.filter((c) => selectedClaimIds.has(c.claim_id));
    if (!targetClaims.length) {
      setErrorMsg('Please select at least one checkable claim assertion to verify.');
      return;
    }

    setVerifying(true);
    try {
      const payload = {
        claims: targetClaims,
        use_demo_evidence: useSampleFallback,
      };

      const resp = await axios.post(`${API_BASE_URL}/api/verify/${targetCondition}`, payload);
      const verifiedList = resp.data.claims || [];
      setResults(verifiedList);

      // Record in session history
      if (onVerificationComplete && verifiedList.length > 0) {
        onVerificationComplete(verifiedList, targetCondition);
      }
    } catch (err) {
      if (err.response?.status === 503 && err.response?.data?.details) {
        setIsOfflineService(true);
        setErrorMsg(err.response.data.details);
        if (err.response?.data?.claims) {
          setResults(err.response.data.claims);
        }
      } else {
        setErrorMsg(
          err.response?.data?.details ||
          err.response?.data?.error ||
          err.message ||
          'Verification request failed.'
        );
      }
    } finally {
      setVerifying(false);
    }
  };

  // Quick 1-Click Run from Presets
  const handleQuickRunSample = async (sample) => {
    setInputTab('text');
    setArticleText(sample.text);
    const mockClaim = {
      claim_id: 'CLM-01',
      claim_text: sample.text,
    };
    setClaims([mockClaim]);
    setSelectedClaimIds(new Set(['CLM-01']));
    setResults([]);
    setErrorMsg('');
    setIsOfflineService(false);

    // Trigger verification directly
    setVerifying(true);
    try {
      const payload = {
        claims: [mockClaim],
        use_demo_evidence: useSampleFallback,
      };
      const resp = await axios.post(`${API_BASE_URL}/api/verify/${activeCondition}`, payload);
      const verifiedList = resp.data.claims || [];
      setResults(verifiedList);
      if (onVerificationComplete && verifiedList.length > 0) {
        onVerificationComplete(verifiedList, activeCondition);
      }
    } catch (err) {
      if (err.response?.status === 503 && err.response?.data?.details) {
        setIsOfflineService(true);
        setErrorMsg(err.response.data.details);
        if (err.response?.data?.claims) {
          setResults(err.response.data.claims);
        }
      } else {
        setErrorMsg(err.response?.data?.error || err.message);
      }
    } finally {
      setVerifying(false);
    }
  };

  const toggleEvidenceExpand = (claimId, index) => {
    const key = `${claimId}-${index}`;
    setExpandedEvidence((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="workbench-page">
      {/* Top Controls Toolbar */}
      <div className="workbench-toolbar">
        <div className="toolbar-left">
          <span className="toolbar-label">VERIFICATION PARADIGM:</span>
          <div className="paradigm-pill-group">
            <button
              className={`paradigm-pill ${activeCondition === 'evidence' ? 'active' : ''}`}
              onClick={() => setActiveCondition('evidence')}
              title="Condition B: Ground assertions against SEC EDGAR 10-K/8-K regulatory filings"
            >
              <span className="dot" />
              Condition B: SEC Grounded
            </button>
            <button
              className={`paradigm-pill ${activeCondition === 'classifier' ? 'active' : ''}`}
              onClick={() => setActiveCondition('classifier')}
              title="Model B: Pretrained MPNet Transformer representation with calibrated multinomial head (Zero-Evidence ML)"
            >
              <span className="dot" />
              Model B: Supervised Classifier
            </button>
            <button
              className={`paradigm-pill ${activeCondition === 'internal' ? 'active' : ''}`}
              onClick={() => setActiveCondition('internal')}
              title="Condition A: Test local LLM parametric memory without external retrieval"
            >
              <span className="dot" />
              Condition A: Internal Memory
            </button>
          </div>
        </div>

        <div className="toolbar-right">
          <label className="fallback-toggle-pill" title="Enables verified sample Form 10-K filing excerpts if SEC live servers rate-limit">
            <input
              type="checkbox"
              checked={useSampleFallback}
              onChange={(e) => setUseSampleFallback(e.target.checked)}
            />
            <span>Sample Archival Fallback (Offline-Ready)</span>
          </label>
        </div>
      </div>

      {/* Main 2-Column Workbench Grid */}
      <div className="workbench-grid">
        {/* Left Column: News Ingestion & Assertion Extraction */}
        <div className="workbench-col left-col">
          {/* Card 1: Ingestion Panel */}
          <div className="workbench-panel">
            <div className="panel-title-bar">
              <div className="panel-badge">01 · INGESTION</div>
              <h3>Financial News Input</h3>
            </div>

            {/* Quick Preset Buttons */}
            <div className="quick-presets-strip">
              <span className="presets-label">Presets:</span>
              <div className="preset-chips">
                {PRESET_SAMPLES.map((sample) => (
                  <button
                    key={sample.id}
                    className="preset-chip"
                    onClick={() => {
                      setInputTab('text');
                      setArticleText(sample.text);
                      const generated = [{ claim_id: 'CLM-01', claim_text: sample.text }];
                      setClaims(generated);
                      setSelectedClaimIds(new Set(['CLM-01']));
                      setResults([]);
                    }}
                    title={sample.summary}
                  >
                    {sample.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Input Mode Selector */}
            <div className="input-mode-tabs">
              <button
                className={`mode-tab ${inputTab === 'text' ? 'active' : ''}`}
                onClick={() => setInputTab('text')}
              >
                Paste News Text
              </button>
              <button
                className={`mode-tab ${inputTab === 'url' ? 'active' : ''}`}
                onClick={() => setInputTab('url')}
              >
                Article URL
              </button>
              <button
                className={`mode-tab ${inputTab === 'file' ? 'active' : ''}`}
                onClick={() => setInputTab('file')}
              >
                Upload Document
              </button>
            </div>

            {/* Input Forms */}
            <form onSubmit={handleExtractArticle} className="workbench-form">
              {inputTab === 'text' && (
                <div className="textarea-wrapper">
                  <textarea
                    className="workbench-textarea"
                    rows="5"
                    value={articleText}
                    onChange={(e) => setArticleText(e.target.value)}
                    placeholder="Paste financial news paragraph, press release, or specific numerical revenue assertion..."
                    disabled={extracting || verifying}
                  />
                  <div className="textarea-footer">
                    <span>{articleText.length} characters · ~{articleText.trim().split(/\s+/).filter(Boolean).length} words</span>
                  </div>
                </div>
              )}

              {inputTab === 'url' && (
                <input
                  type="url"
                  className="workbench-input"
                  value={articleUrl}
                  onChange={(e) => setArticleUrl(e.target.value)}
                  placeholder="https://www.reuters.com/business/finance/..."
                  disabled={extracting || verifying}
                />
              )}

              {inputTab === 'file' && (
                <div className="file-upload-box">
                  <input
                    type="file"
                    accept=".pdf,.docx,.txt,.html,.htm"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    disabled={extracting || verifying}
                  />
                  {selectedFile && (
                    <div className="file-info-pill">
                      Selected: <b>{selectedFile.name}</b> ({(selectedFile.size / 1024).toFixed(1)} KB)
                    </div>
                  )}
                </div>
              )}

              <div className="form-action-row">
                <button
                  type="submit"
                  className="btn-extract-primary"
                  disabled={extracting || verifying}
                >
                  {extracting ? 'Segmenting Claims...' : 'Extract Checkable Claims'}
                </button>
                {articleText && (
                  <button
                    type="button"
                    className="btn-clear-text"
                    onClick={() => {
                      setArticleText('');
                      setClaims([]);
                      setResults([]);
                    }}
                  >
                    Clear
                  </button>
                )}
              </div>
            </form>

            {errorMsg && <div className="alert-box-error">{errorMsg}</div>}
          </div>

          {/* Card 2: Extracted Claims Checklist */}
          <div className="workbench-panel">
            <div className="panel-title-bar">
              <div className="panel-badge">02 · CLAIMS</div>
              <h3>Checkable Assertions ({claims.length})</h3>
              <div className="claim-batch-actions">
                <button type="button" onClick={selectAllClaims}>All</button>
                <span>·</span>
                <button type="button" onClick={deselectAllClaims}>None</button>
                <span className="selected-tag">{selectedClaimIds.size} selected</span>
              </div>
            </div>

            {claims.length === 0 ? (
              <div className="empty-claims-notice">
                <span>⚡ No claims extracted yet. Click "Extract Checkable Claims" above or choose a preset.</span>
              </div>
            ) : (
              <div className="claims-scroll-list">
                {claims.map((claim) => {
                  const isChecked = selectedClaimIds.has(claim.claim_id);
                  return (
                    <div
                      key={claim.claim_id}
                      className={`claim-row-card ${isChecked ? 'is-selected' : ''}`}
                      onClick={() => toggleClaim(claim.claim_id)}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => {}}
                        className="claim-check"
                      />
                      <div className="claim-text-wrap">
                        <span className="claim-idx">{claim.claim_id}</span>
                        <p className="claim-body">{claim.claim_text}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {claims.length > 0 && (
              <div className="verify-action-footer">
                <div className="inline-mode-selector">
                  <span className="mode-select-label">VERIFICATION MODE:</span>
                  <div className="inline-mode-tabs">
                    <button
                      type="button"
                      className={`inline-mode-tab ${activeCondition === 'evidence' ? 'active' : ''}`}
                      onClick={() => setActiveCondition('evidence')}
                    >
                      Condition B: SEC Grounded
                    </button>
                    <button
                      type="button"
                      className={`inline-mode-tab ${activeCondition === 'classifier' ? 'active' : ''}`}
                      onClick={() => setActiveCondition('classifier')}
                    >
                      Model B: Supervised Classifier
                    </button>
                    <button
                      type="button"
                      className={`inline-mode-tab ${activeCondition === 'internal' ? 'active' : ''}`}
                      onClick={() => setActiveCondition('internal')}
                    >
                      Condition A: Parametric LLM
                    </button>
                  </div>
                </div>

                <button
                  type="button"
                  className="btn-verify-main"
                  onClick={() => handleVerify(activeCondition)}
                  disabled={verifying || selectedClaimIds.size === 0}
                >
                  {verifying
                    ? `Verifying ${selectedClaimIds.size} claim(s) via ${activeCondition === 'evidence' ? 'SEC Filings' : activeCondition === 'classifier' ? 'Supervised MPNet' : 'Parametric Memory'}...`
                    : `Verify Selected Claims (${selectedClaimIds.size} Selected)`}
                </button>
                {verifying && (
                  <div className="progress-bar-linear">
                    <div className="progress-inner" />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Verification Inspector & Evidence Citations */}
        <div className="workbench-col right-col">
          {results.length > 0 ? (
            <div className="workbench-panel results-panel">
              <div className="panel-title-bar">
                <div className="panel-badge badge-success">03 · VERIFICATION AUDIT</div>
                <h3>Fact-Checking Decisions & Evidence Citations</h3>
                <span className="active-cond-badge">
                  {activeCondition === 'evidence'
                    ? 'Condition B (Grounded)'
                    : activeCondition === 'classifier'
                    ? 'Model B (Supervised MPNet)'
                    : 'Condition A (Internal)'}
                </span>
              </div>

              {isOfflineService && (
                <div className="offline-service-banner">
                  <div className="banner-icon">⚠️</div>
                  <div className="banner-content">
                    <strong>Local Ollama Service is Offline</strong>
                    <p>{errorMsg}</p>
                    <div>
                      <span>Quick commands in an external terminal:</span>
                      <code>1. ollama serve</code>
                      <code>2. ollama run qwen2.5:3b</code>
                    </div>
                  </div>
                </div>
              )}

              <div className="results-scroll-container">
                {results.map((item) => {
                  const verdict = item.status === 'error' ? 'ERROR' : (item.verdict || 'UNVERIFIABLE');
                  const isError = item.status === 'error';
                  const badgeClass = isError ? 'badge-error' : `badge-${verdict.toLowerCase()}`;

                  return (
                    <div key={item.claim_id} className="verdict-audit-card">
                      {/* Top bar with verdict and confidence */}
                      <div className="audit-card-top">
                        <div className="verdict-display">
                          <span className={`verdict-pill-large ${badgeClass}`}>
                            {verdict}
                          </span>
                          {item.confidence !== null && item.confidence !== undefined && (
                            <div
                              className="confidence-meter-chip"
                              title={item.confidence_type === 'CALIBRATED_MULTINOMIAL_PROBABILITY'
                                ? "Calibrated multinomial probability output by the logistic regression classifier head"
                                : "Model self-reported numerical score (uncalibrated float in [0.0, 1.0])"
                              }
                            >
                              <span className="meter-label">
                                {item.confidence_type === 'CALIBRATED_MULTINOMIAL_PROBABILITY' ? 'Class Probability:' : 'Model Certainty:'}
                              </span>
                              <strong>{(item.confidence * 100).toFixed(item.confidence_type === 'CALIBRATED_MULTINOMIAL_PROBABILITY' ? 1 : 0)}%</strong>
                              <span className={item.confidence_type === 'CALIBRATED_MULTINOMIAL_PROBABILITY' ? 'calibrated-sub' : 'uncalibrated-sub'}>
                                {item.confidence_type === 'CALIBRATED_MULTINOMIAL_PROBABILITY' ? '(calibrated)' : '(uncalibrated)'}
                              </span>
                            </div>
                          )}
                        </div>
                        <span className="audit-claim-id">{item.claim_id}</span>
                      </div>

                      {/* Source Mode Badge */}
                      <div className="audit-source-mode-row">
                        {item.condition === 'classifier' && (
                          <span className="source-mode-pill mode-classifier" title="Evaluated using Pretrained MPNet (110M params) Supervised Classifier">
                            ⚡ Mode: Supervised Classifier (all-mpnet-base-v2)
                          </span>
                        )}
                        {item.source_mode === 'LIVE_EXTERNAL' && (
                          <span className="source-mode-pill mode-live" title="Live regulatory filings extracted from SEC EDGAR">
                            <span className="dot" /> Mode: Live SEC EDGAR Retrieval
                          </span>
                        )}
                        {item.source_mode === 'OFFLINE_SAMPLE_ARCHIVE' && (
                          <span className="source-mode-pill mode-archive" title="Audited SEC Form 10-K/8-K filing excerpt loaded from verified offline archive">
                            🏛️ Mode: Offline Archival Sample (Audited SEC Form 10-K)
                          </span>
                        )}
                        {item.source_mode === 'RETRIEVAL_FAILED' && (
                          <span className="source-mode-pill mode-failed" title="Live retrieval returned a hard API or network error">
                            ⚠️ Mode: Live Retrieval Failed
                          </span>
                        )}
                        {item.source_mode === 'PARAMETRIC_INTERNAL_MEMORY' && (
                          <span className="source-mode-pill mode-parametric" title="Evaluated exclusively using internal model weights">
                            🧠 Mode: Parametric LLM Memory (Zero-Shot)
                          </span>
                        )}
                      </div>

                      {/* Claim Text */}
                      <div className="evaluated-statement-box">
                        <span className="statement-lbl">Evaluated Assertion:</span>
                        <p className="statement-text">"{item.claim_text}"</p>
                      </div>

                      {/* Supervised Classifier Multi-Class Probabilities Grid */}
                      {item.probabilities && (
                        <div className="classifier-prob-grid">
                          <div className={`prob-card ${item.verdict === 'SUPPORTED' ? 'active-prob' : ''}`}>
                            <span className="prob-lbl">SUPPORTED</span>
                            <div className="prob-val">{(item.probabilities.SUPPORTED * 100).toFixed(1)}%</div>
                          </div>
                          <div className={`prob-card ${item.verdict === 'REFUTED' ? 'active-prob' : ''}`}>
                            <span className="prob-lbl">REFUTED</span>
                            <div className="prob-val">{(item.probabilities.REFUTED * 100).toFixed(1)}%</div>
                          </div>
                          <div className={`prob-card ${item.verdict === 'UNVERIFIABLE' ? 'active-prob' : ''}`}>
                            <span className="prob-lbl">UNVERIFIABLE</span>
                            <div className="prob-val">{(item.probabilities.UNVERIFIABLE * 100).toFixed(1)}%</div>
                          </div>
                        </div>
                      )}

                      {/* Supervised Classifier Methodology Disclaimer */}
                      {item.condition === 'classifier' && (
                        <div className="classifier-disclaimer-banner">
                          <span className="disclaimer-icon">ℹ️</span>
                          <span>
                            <strong>Supervised Machine Learning Prediction:</strong> Computed via 768-d MPNet semantic embedding and calibrated multinomial head. This model assesses linguistic and contextual plausibility and does not retrieve or cite external documents.
                          </span>
                        </div>
                      )}

                      {/* Retrieval notice if fallback was used */}
                      {item.retrieval_notice && (
                        <div className="notice-banner-archival">
                          <span className="icon">🏛️</span>
                          <span>{item.retrieval_notice}</span>
                        </div>
                      )}

                      {/* Model Rationale */}
                      {item.explanation && (
                        <div className="model-rationale-box">
                          <span className="rationale-lbl">Model Reasoning & Verification Rationale:</span>
                          <p className="rationale-text">{item.explanation}</p>
                        </div>
                      )}

                      {/* Diagnostic errors if live retrieval failed */}
                      {item.evidence_errors && item.evidence_errors.some((e) => e.status === 'error') && (
                        <div className="diagnostic-failure-card">
                          <strong>Retrieval Audit:</strong>
                          <ul>
                            {item.evidence_errors
                              .filter((e) => e.status === 'error')
                              .map((err, i) => (
                                <li key={i}>
                                  <b>{err.source}:</b> {err.error}
                                </li>
                              ))}
                          </ul>
                        </div>
                      )}

                      {/* Cited Evidence Cards */}
                      {item.evidence && item.evidence.length > 0 && (
                        <div className="cited-filings-section">
                          <div className="filings-header">
                            <span className="filings-title">
                              Cited Regulatory Evidence ({item.evidence.length})
                            </span>
                            <span className="temporal-tag">
                              Temporal Integrity: {item.temporal_validation === 'valid' ? 'Valid (Pre-dates Claim)' : 'Undetermined'}
                            </span>
                          </div>

                          <div className="filings-cards-list">
                            {item.evidence.map((source, index) => {
                              const key = `${item.claim_id}-${index}`;
                              const isExpanded = expandedEvidence[key];
                              return (
                                <div key={key} className="filing-evidence-card">
                                  <div className="filing-top">
                                    <strong className="filing-source">{source.source}</strong>
                                    <span className="filing-date">Date: {source.evidence_date}</span>
                                  </div>

                                  <p className="filing-body">
                                    {isExpanded || source.evidence_text.length <= 180
                                      ? source.evidence_text
                                      : `${source.evidence_text.slice(0, 180)}...`}
                                  </p>

                                  <div className="filing-bottom">
                                    {source.evidence_text.length > 180 && (
                                      <button
                                        type="button"
                                        className="btn-expand-filing"
                                        onClick={() => toggleEvidenceExpand(item.claim_id, index)}
                                      >
                                        {isExpanded ? 'Collapse ▴' : 'Show Full Filing Excerpt ▾'}
                                      </button>
                                    )}
                                    {source.url && (
                                      <a
                                        href={source.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="filing-sec-link"
                                      >
                                        Open SEC Filing ↗
                                      </a>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Standby Guide & 1-Click Interactive Benchmark Hub */
            <div className="workbench-panel standby-panel">
              <div className="standby-header">
                <div className="panel-badge">INSPECTOR STANDBY</div>
                <h3>Interactive Verification Hub</h3>
                <p>Run a verification using the left panel or click any preset below to instantly see live evidence grounding in action.</p>
              </div>

              <div className="quick-test-cards-grid">
                {PRESET_SAMPLES.map((sample) => (
                  <div
                    key={sample.id}
                    className="quick-test-card"
                    onClick={() => handleQuickRunSample(sample)}
                  >
                    <div className="card-badge-row">
                      <span className="company-badge">{sample.company}</span>
                      <span className={`ground-truth-badge truth-${sample.truth.toLowerCase()}`}>
                        {sample.truthBadge}
                      </span>
                    </div>
                    <h4>{sample.label}</h4>
                    <p className="quick-claim-snippet">"{sample.text}"</p>
                    <div className="card-action-hint">
                      <span>Click to verify with SEC Grounding →</span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="pipeline-info-box">
                <div className="info-step">
                  <span className="step-badge-mini">1</span>
                  <div>
                    <strong>Targeted Company Identification</strong>
                    <p>Resolves entity to official SEC CIK (e.g. Apple CIK 0000320193).</p>
                  </div>
                </div>
                <div className="info-step">
                  <span className="step-badge-mini">2</span>
                  <div>
                    <strong>XBRL & Form 10-K Retrieval</strong>
                    <p>Matches Revenue and Buyback concepts with pre-claim date boundaries.</p>
                  </div>
                </div>
                <div className="info-step">
                  <span className="step-badge-mini">3</span>
                  <div>
                    <strong>Constrained Evaluation</strong>
                    <p>LLM is forced to verify strictly against regulatory disclosures.</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
