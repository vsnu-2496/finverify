import React from 'react';

export default function Topbar({ currentPage, setCurrentPage, health, onNewVerification }) {
  const titles = {
    overview: {
      title: 'Platform Overview',
      subtitle: 'Evidence-grounded vs. parametric financial news misinformation verification',
    },
    verify: {
      title: 'Verify Financial News',
      subtitle: 'Extract checkable assertions and evaluate against SEC filings and local LLM',
    },
    history: {
      title: 'Verification History',
      subtitle: 'Inspect session verification decisions, confidence scores, and retrieved evidence',
    },
    analytics: {
      title: 'Verification Analytics',
      subtitle: 'Empirical distribution and decision breakdowns across verification sessions',
    },
    research: {
      title: 'Research Experiments & Benchmarks',
      subtitle: '300-claim Fin-Fact study comparing Qwen2.5:3b against Pretrained MPNet Classifier',
    },
    settings: {
      title: 'System Settings & Configuration',
      subtitle: 'Model defaults, regulatory data sources, and session data management',
    },
  };

  const currentInfo = titles[currentPage] || titles.overview;

  return (
    <header className="app-topbar">
      <div className="topbar-inner-container">
        <div className="topbar-left">
          <div className="breadcrumb">
            <span className="breadcrumb-root">FINVERIFY AI</span>
            <span className="breadcrumb-sep">/</span>
            <span className="breadcrumb-current">{currentInfo.title}</span>
          </div>
          <h1 className="topbar-page-title">{currentInfo.title}</h1>
          <p className="topbar-subtitle">{currentInfo.subtitle}</p>
        </div>

      <div className="topbar-right">
        <div className="topbar-status-group">
          <span className={`pill-badge ${health.status === 'ok' ? 'pill-online' : 'pill-offline'}`}>
            <span className="dot" />
            {health.status === 'ok' ? 'Backend Online' : 'Connecting...'}
          </span>
          <span className="pill-badge pill-model" title="Local zero-shot generative model">
            Ollama · qwen2.5:3b
          </span>
          <span className="pill-badge pill-classifier" title="Pretrained transformer classifier">
            MPNet · Supervised
          </span>
        </div>

        {currentPage !== 'verify' && (
          <button
            className="action-btn-primary"
            onClick={() => {
              setCurrentPage('verify');
              window.location.hash = 'verify';
              if (onNewVerification) onNewVerification();
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ display: 'inline-block', verticalAlign: '-2px', marginRight: '6px' }}>
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Verify Claim
          </button>
        )}

        <button
          className={`topbar-icon-btn ${currentPage === 'settings' ? 'active' : ''}`}
          onClick={() => {
            setCurrentPage('settings');
            window.location.hash = 'settings';
          }}
          title="Open Settings & Info"
          aria-label="Settings"
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </div>
      </div>
    </header>
  );
}
