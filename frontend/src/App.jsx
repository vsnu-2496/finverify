import React, { useEffect, useState } from 'react';
import axios from 'axios';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import OverviewPage from './pages/OverviewPage';
import VerifyNewsPage from './pages/VerifyNewsPage';
import HistoryPage from './pages/HistoryPage';
import AnalyticsPage from './pages/AnalyticsPage';
import ResearchPage from './pages/ResearchPage';
import SettingsPage from './pages/SettingsPage';
import VerificationDetailsModal from './components/VerificationDetailsModal';

const API_BASE_URL = 'http://127.0.0.1:5000';
const LOCAL_STORAGE_KEY = 'finverify_session_history_v2';

export default function App() {
  // Page Routing State (overview | verify | history | analytics | research | settings)
  const [currentPage, setCurrentPage] = useState(() => {
    const hash = window.location.hash.replace('#', '').toLowerCase();
    if (['overview', 'verify', 'history', 'analytics', 'research', 'settings'].includes(hash)) {
      return hash;
    }
    return 'overview';
  });

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [health, setHealth] = useState({ status: 'loading', message: 'Connecting to backend...' });
  const [latestResearch, setLatestResearch] = useState(null);

  // Inspector modal record state
  const [inspectRecord, setInspectRecord] = useState(null);

  // Claim to rerun in workbench
  const [rerunClaimText, setRerunClaimText] = useState('');

  // Session History State (synced with localStorage & backend)
  const [history, setHistory] = useState(() => {
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Sync with browser hash changes (Back/Forward navigation)
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '').toLowerCase();
      if (['overview', 'verify', 'history', 'analytics', 'research', 'settings'].includes(hash)) {
        setCurrentPage(hash);
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Poll backend health & research data
  const refreshBackend = async () => {
    try {
      const [hResp, rResp] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/health`),
        axios.get(`${API_BASE_URL}/api/research/results/latest`),
      ]);
      setHealth(hResp.data);
      setLatestResearch(rResp.data);
    } catch (err) {
      setHealth({ status: 'offline', message: err.message });
    }
  };

  useEffect(() => {
    refreshBackend();
    // Load stored backend session history
    axios
      .get(`${API_BASE_URL}/api/history`)
      .then((res) => {
        if (res.data?.history?.length > 0) {
          setHistory((prev) => {
            const existingKeys = new Set(prev.map((p) => `${p.claim_text}-${p.timestamp}`));
            const merged = [...prev];
            for (const item of res.data.history) {
              const key = `${item.claim_text}-${item.timestamp}`;
              if (!existingKeys.has(key)) {
                merged.push(item);
                existingKeys.add(key);
              }
            }
            return merged.slice(0, 150);
          });
        }
      })
      .catch(() => {});
  }, []);

  // Save history to localStorage whenever updated
  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(history));
    } catch {
      // Storage full or unavailable
    }
  }, [history]);

  // Handler when claims are verified on VerifyNewsPage
  const handleVerificationComplete = (verifiedClaims, condition) => {
    const newItems = verifiedClaims.map((c) => ({
      ...c,
      condition,
      timestamp: new Date().toISOString(),
    }));

    setHistory((prev) => {
      const updated = [...newItems, ...prev].slice(0, 150);
      return updated;
    });

    // Sync with backend history
    axios.post(`${API_BASE_URL}/api/history`, { items: newItems }).catch(() => {});
  };

  // Handler to delete a single history item
  const handleDeleteHistoryItem = (claimText, timestamp) => {
    const updated = history.filter(
      (h) => !(h.claim_text === claimText && h.timestamp === timestamp)
    );
    setHistory(updated);
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(updated));
    } catch {}
    // Sync updated list with backend
    axios.put(`${API_BASE_URL}/api/history`, { items: updated }).catch(() => {});
  };

  // Handler to clear history
  const handleClearHistory = () => {
    setHistory([]);
    try {
      localStorage.removeItem(LOCAL_STORAGE_KEY);
    } catch {}
    axios.delete(`${API_BASE_URL}/api/history`).catch(() => {});
  };

  // Handler to rerun a claim in workbench
  const handleRerunClaim = (claimText) => {
    setRerunClaimText(claimText);
    setCurrentPage('verify');
    window.location.hash = 'verify';
  };

  return (
    <div className={`app-container ${sidebarCollapsed ? 'sidebar-is-collapsed' : ''}`}>
      {/* Collapsible Left Sidebar */}
      <Sidebar
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        collapsed={sidebarCollapsed}
        setCollapsed={setSidebarCollapsed}
        historyCount={history.length}
        health={health}
      />

      {/* Main Content Area */}
      <div className="app-main-area">
        {/* Top Navigation Bar */}
        <Topbar
          currentPage={currentPage}
          setCurrentPage={setCurrentPage}
          health={health}
          onNewVerification={() => {
            setCurrentPage('verify');
            window.location.hash = 'verify';
          }}
        />

        {/* Page Routing Switcher */}
        <main className="app-content-body">
          <div className="content-max-width-wrapper">
            {currentPage === 'overview' && (
              <OverviewPage
                setCurrentPage={setCurrentPage}
                history={history}
                measuredResearch={latestResearch?.measured_research}
                modelComparison={latestResearch?.model_comparison}
                onOpenDetails={(item) => setInspectRecord(item)}
                onRerun={handleRerunClaim}
              />
            )}

            {currentPage === 'verify' && (
              <VerifyNewsPage
                onVerificationComplete={handleVerificationComplete}
                initialClaimText={rerunClaimText}
              />
            )}

            {currentPage === 'history' && (
              <HistoryPage
                history={history}
                onClearHistory={handleClearHistory}
                onDeleteItem={handleDeleteHistoryItem}
                onOpenDetails={(item) => setInspectRecord(item)}
                onRerun={handleRerunClaim}
              />
            )}

            {currentPage === 'analytics' && (
              <AnalyticsPage
                history={history}
                measuredResearch={latestResearch?.measured_research}
                modelComparison={latestResearch?.model_comparison}
                onNavigateVerify={() => {
                  setCurrentPage('verify');
                  window.location.hash = 'verify';
                }}
              />
            )}

            {currentPage === 'research' && (
              <ResearchPage
                measuredResearch={latestResearch?.measured_research}
                modelComparison={latestResearch?.model_comparison}
                latestResults={latestResearch}
                onRefreshResearch={refreshBackend}
              />
            )}

            {currentPage === 'settings' && (
              <SettingsPage
                history={history}
                onClearHistory={handleClearHistory}
                health={health}
              />
            )}
          </div>
        </main>

        {/* Footer */}
        <footer className="app-footer">
          <div className="footer-max-width-wrapper">
            <div className="footer-content">
              <span>FinVerify AI · Evidence-Grounded Misinformation Detection Suite</span>
              <div className="footer-links">
                <span>Model A: Qwen2.5:3b (Parametric)</span>
                <span className="dot-sep">•</span>
                <span>Model B: all-mpnet-base-v2 (Supervised)</span>
                <span className="dot-sep">•</span>
                <span>Grounding: SEC EDGAR Form 10-K/8-K</span>
              </div>
            </div>
          </div>
        </footer>
      </div>

      {/* Global Details & Evidence Inspector Modal */}
      {inspectRecord && (
        <VerificationDetailsModal
          record={inspectRecord}
          onClose={() => setInspectRecord(null)}
          onRerun={handleRerunClaim}
        />
      )}
    </div>
  );
}
