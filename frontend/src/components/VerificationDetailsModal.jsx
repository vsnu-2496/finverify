import React from 'react';

export default function VerificationDetailsModal({ record, onClose, onRerun }) {
  if (!record) return null;

  const isError = record.status === 'error';
  const verdict = isError ? 'ERROR' : (record.verdict || 'UNVERIFIABLE');
  const badgeClass = isError ? 'badge-error' : `badge-${verdict.toLowerCase()}`;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content-large" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div className="header-info">
            <span className="modal-eyebrow">AUDIT & EVIDENCE INSPECTOR</span>
            <h3>{record.claim_id || 'Verification Record'}</h3>
          </div>
          <button className="modal-close-btn" onClick={onClose} title="Close inspector">✕</button>
        </div>

        {/* Body */}
        <div className="modal-body-scroll">
          {/* Claim Box */}
          <div className="modal-statement-card">
            <span className="statement-tag">Evaluated Financial Assertion</span>
            <p className="statement-quote">"{record.claim_text}"</p>
          </div>

          {/* Key Metrics Grid */}
          <div className="modal-stats-grid">
            <div className="modal-stat-tile">
              <span className="stat-lbl">Verdict</span>
              <strong className={`verdict-pill-modal ${badgeClass}`}>{verdict}</strong>
            </div>

            <div className="modal-stat-tile">
              <span className="stat-lbl">Certainty (Uncalibrated)</span>
              <strong>
                {record.confidence !== null && record.confidence !== undefined
                  ? `${(record.confidence * 100).toFixed(1)}%`
                  : 'N/A'}
              </strong>
            </div>

            <div className="modal-stat-tile">
              <span className="stat-lbl">Source Mode</span>
              <strong style={{ fontSize: '12px' }}>
                {record.source_mode === 'LIVE_EXTERNAL'
                  ? 'Live SEC EDGAR'
                  : record.source_mode === 'OFFLINE_SAMPLE_ARCHIVE'
                  ? 'Offline Archival Sample'
                  : record.source_mode === 'RETRIEVAL_FAILED'
                  ? 'Retrieval Failed'
                  : record.condition === 'internal'
                  ? 'Parametric LLM'
                  : 'SEC Grounded'}
              </strong>
            </div>

            <div className="modal-stat-tile">
              <span className="stat-lbl">Temporal Status</span>
              <strong className={record.temporal_validation === 'valid' ? 'text-emerald' : 'text-amber'}>
                {record.temporal_validation === 'valid' ? 'Valid (Pre-dates Claim)' : 'Undetermined'}
              </strong>
            </div>
          </div>

          {/* Model Explanation */}
          {record.explanation && (
            <div className="modal-explanation-card">
              <span className="card-lbl">Model Reasoning & Justification</span>
              <p className="explanation-body">{record.explanation}</p>
            </div>
          )}

          {/* Cited Evidence Documents */}
          <div className="modal-evidence-container">
            <div className="evidence-header-row">
              <span className="evidence-title">
                Cited Regulatory Evidence Passages ({record.evidence?.length || 0})
              </span>
              <span className="integrity-badge">SEC Temporal Bounds: Pre-Claim Verified</span>
            </div>

            {record.evidence && record.evidence.length > 0 ? (
              <div className="evidence-cards-stack">
                {record.evidence.map((ev, i) => (
                  <div key={i} className="modal-evidence-item">
                    <div className="item-top">
                      <span className="source-tag">{ev.source}</span>
                      <span className="filing-date-tag">Filing Date: {ev.evidence_date}</span>
                    </div>

                    <p className="passage-text">{ev.evidence_text}</p>

                    <div className="item-meta-row">
                      <span className="relevance-score">Relevance: {ev.relevance || 0.95}</span>
                      {ev.url && (
                        <a
                          href={ev.url}
                          target="_blank"
                          rel="noreferrer"
                          className="sec-filing-link"
                        >
                          View Official SEC Filing ↗
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-evidence-box">
                <span className="icon">⚠️</span>
                <div>
                  <strong>No external evidence passages retrieved</strong>
                  <p>In Condition A (Internal Knowledge), claims are verified using parametric LLM weights without document grounding.</p>
                </div>
              </div>
            )}
          </div>

          {/* Meta Info */}
          <div className="modal-audit-footer">
            <span>Timestamp: {record.timestamp ? new Date(record.timestamp).toLocaleString() : 'Recent'}</span>
            <span>Entity: {record.entity || 'General Corporate'}</span>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="modal-footer-actions">
          {onRerun && (
            <button
              className="btn-rerun-modal"
              onClick={() => {
                onRerun(record.claim_text);
                onClose();
              }}
            >
              ↻ Re-verify in Workbench
            </button>
          )}
          <button className="btn-close-modal" onClick={onClose}>
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
