import React, { useState, useMemo } from 'react';
import ConfirmationDialog from '../components/ConfirmationDialog';

export default function HistoryPage({ history, onClearHistory, onDeleteItem, onOpenDetails, onRerun }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterVerdict, setFilterVerdict] = useState('ALL');
  const [filterCondition, setFilterCondition] = useState('ALL');
  const [sortBy, setSortBy] = useState('newest'); // 'newest' | 'oldest' | 'highest_conf' | 'lowest_conf'
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 8;

  // Confirmation dialog states
  const [deleteConfirmItem, setDeleteConfirmItem] = useState(null);
  const [clearAllConfirm, setClearAllConfirm] = useState(false);

  // Filtered & Sorted Records
  const processedRecords = useMemo(() => {
    let result = [...history];

    // Search filter
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      result = result.filter((item) => item.claim_text?.toLowerCase().includes(q));
    }

    // Verdict filter
    if (filterVerdict !== 'ALL') {
      if (filterVerdict === 'ERROR') {
        result = result.filter((item) => item.status === 'error');
      } else if (filterVerdict === 'INCONCLUSIVE') {
        result = result.filter((item) => item.verdict === 'UNVERIFIABLE' || item.verdict === 'INCONCLUSIVE');
      } else {
        result = result.filter((item) => item.verdict === filterVerdict);
      }
    }

    // Condition filter
    if (filterCondition !== 'ALL') {
      result = result.filter((item) => item.condition === filterCondition);
    }

    // Sorting
    result.sort((a, b) => {
      if (sortBy === 'newest') {
        return new Date(b.timestamp || 0) - new Date(a.timestamp || 0);
      }
      if (sortBy === 'oldest') {
        return new Date(a.timestamp || 0) - new Date(b.timestamp || 0);
      }
      if (sortBy === 'highest_conf') {
        return (b.confidence || 0) - (a.confidence || 0);
      }
      if (sortBy === 'lowest_conf') {
        return (a.confidence || 0) - (b.confidence || 0);
      }
      return 0;
    });

    return result;
  }, [history, searchTerm, filterVerdict, filterCondition, sortBy]);

  // Pagination calculation
  const totalPages = Math.ceil(processedRecords.length / pageSize) || 1;
  const paginatedRecords = processedRecords.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // Export functions
  const exportHistoryJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(history, null, 2));
    const a = document.createElement('a');
    a.href = dataStr;
    a.download = `finverify_history_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const exportHistoryCSV = () => {
    const headers = ['Timestamp', 'Claim_ID', 'Verdict', 'Confidence', 'Condition', 'Claim_Text', 'Evidence_Count'];
    const rows = history.map((item) => [
      `"${item.timestamp || ''}"`,
      `"${item.claim_id || ''}"`,
      `"${item.verdict || ''}"`,
      item.confidence || 0,
      `"${item.condition || ''}"`,
      `"${(item.claim_text || '').replace(/"/g, '""')}"`,
      item.evidence?.length || 0,
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const a = document.createElement('a');
    a.href = encodeURI(csvContent);
    a.download = `finverify_history_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="history-page-container">
      {/* Header Bar */}
      <div className="history-hero-header">
        <div className="header-info">
          <h2>Verification Session Log</h2>
          <p>
            Review all claims evaluated during this session. Search assertions, filter by verdict, inspect regulatory evidence, or export audit files.
          </p>
        </div>

        <div className="header-actions-group">
          {history.length > 0 && (
            <>
              <button className="btn-export-outline" onClick={exportHistoryJSON} title="Download complete JSON export">
                Export JSON ⤓
              </button>
              <button className="btn-export-outline" onClick={exportHistoryCSV} title="Download CSV spreadsheet">
                Export CSV ⤓
              </button>
              <button className="btn-clear-danger" onClick={() => setClearAllConfirm(true)}>
                Clear Log
              </button>
            </>
          )}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="history-controls-panel">
        <div className="search-field-wrap">
          <span className="search-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </span>
          <input
            type="text"
            className="history-search-input"
            placeholder="Search claims by keyword (e.g. Apple, revenue, buyback)..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setCurrentPage(1);
            }}
          />
          {searchTerm && (
            <button className="clear-search-btn" onClick={() => setSearchTerm('')}>✕</button>
          )}
        </div>

        <div className="filters-row">
          {/* Verdict Filter */}
          <div className="filter-group">
            <span className="filter-lbl">Verdict:</span>
            <div className="filter-pill-stack">
              {['ALL', 'SUPPORTED', 'REFUTED', 'INCONCLUSIVE', 'ERROR'].map((v) => (
                <button
                  key={v}
                  className={`filter-pill-btn ${filterVerdict === v ? 'active' : ''}`}
                  onClick={() => {
                    setFilterVerdict(v);
                    setCurrentPage(1);
                  }}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>

          {/* Condition Filter */}
          <div className="filter-group">
            <span className="filter-lbl">Paradigm:</span>
            <select
              className="history-select"
              value={filterCondition}
              onChange={(e) => {
                setFilterCondition(e.target.value);
                setCurrentPage(1);
              }}
            >
              <option value="ALL">All Paradigms</option>
              <option value="evidence">Condition B (SEC Grounded)</option>
              <option value="internal">Condition A (Internal Memory)</option>
            </select>
          </div>

          {/* Sort By */}
          <div className="filter-group">
            <span className="filter-lbl">Sort By:</span>
            <select
              className="history-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="highest_conf">Highest Confidence</option>
              <option value="lowest_conf">Lowest Confidence</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Table / Empty State */}
      <div className="history-table-card">
        {processedRecords.length === 0 ? (
          <div className="empty-history-box">
            <span className="empty-icon-large">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--ink-dim)' }}>
                <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
                <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
                <path d="M9 12h6" />
                <path d="M9 16h6" />
              </svg>
            </span>
            <h4>{history.length === 0 ? 'No verification records in this session' : 'No matching records found'}</h4>
            <p>
              {history.length === 0
                ? 'Verify news claims using the Verify News workbench to populate this history log.'
                : 'Try modifying your search keywords or switching filters to show all records.'}
            </p>
            {history.length === 0 && (
              <button
                className="btn-primary-sm"
                onClick={() => {
                  window.location.hash = 'verify';
                }}
              >
                Start Verification
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="table-responsive-wrapper">
              <table className="history-data-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Claim Assertion</th>
                    <th>Paradigm</th>
                    <th>Verdict</th>
                    <th>Confidence</th>
                    <th>Evidence</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedRecords.map((item, index) => {
                    const isError = item.status === 'error';
                    const verdict = isError ? 'ERROR' : (item.verdict || 'UNVERIFIABLE');
                    const badgeClass = isError ? 'badge-error' : `badge-${verdict.toLowerCase()}`;

                    return (
                      <tr key={index} className="history-table-row">
                        <td className="col-time">
                          {item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : 'Recent'}
                        </td>
                        <td className="col-claim">
                          <span className="claim-text-clamp" title={item.claim_text}>
                            {item.claim_text}
                          </span>
                        </td>
                        <td className="col-cond">
                          <span className="paradigm-tag">
                            {item.condition === 'internal' ? 'Condition A' : 'Condition B (SEC)'}
                          </span>
                        </td>
                        <td className="col-verdict">
                          <span className={`verdict-badge-compact ${badgeClass}`}>
                            {verdict}
                          </span>
                        </td>
                        <td className="col-conf">
                          {item.confidence !== null && item.confidence !== undefined
                            ? `${(item.confidence * 100).toFixed(0)}%`
                            : '—'}
                        </td>
                        <td className="col-ev-count">
                          {item.evidence?.length ? (
                            <span className="ev-count-pill">{item.evidence.length} doc(s)</span>
                          ) : (
                            <span className="ev-none-pill">None</span>
                          )}
                        </td>
                        <td className="col-actions" style={{ textAlign: 'right' }}>
                          <button
                            className="btn-action-inspect"
                            onClick={() => onOpenDetails(item)}
                            title="Inspect full evidence passages"
                          >
                            Inspect
                          </button>
                          <button
                            className="btn-action-rerun"
                            onClick={() => onRerun(item.claim_text)}
                            title="Re-run this claim in workbench"
                            aria-label="Rerun verification"
                          >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
                              <path d="M21 3v5h-5" />
                              <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
                              <path d="M3 21v-5h5" />
                            </svg>
                          </button>
                          <button
                            className="btn-action-delete"
                            onClick={() => setDeleteConfirmItem(item)}
                            title="Delete this record"
                            aria-label="Delete record"
                          >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="pagination-bar">
                <span className="pagination-info">
                  Showing {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, processedRecords.length)} of {processedRecords.length} records
                </span>
                <div className="pagination-buttons">
                  <button
                    className="page-btn"
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
                  >
                    ‹ Previous
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((num) => (
                    <button
                      key={num}
                      className={`page-num-btn ${currentPage === num ? 'active' : ''}`}
                      onClick={() => setCurrentPage(num)}
                    >
                      {num}
                    </button>
                  ))}
                  <button
                    className="page-btn"
                    disabled={currentPage === totalPages}
                    onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
                  >
                    Next ›
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Delete Single Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={Boolean(deleteConfirmItem)}
        title="Delete Verification Record?"
        message={`Are you sure you want to remove the verification record for "${deleteConfirmItem?.claim_text?.slice(0, 80)}..."?`}
        confirmText="Delete Record"
        cancelText="Cancel"
        isDanger={true}
        onConfirm={() => {
          if (deleteConfirmItem && onDeleteItem) {
            onDeleteItem(deleteConfirmItem.claim_text, deleteConfirmItem.timestamp);
          }
          setDeleteConfirmItem(null);
        }}
        onCancel={() => setDeleteConfirmItem(null)}
      />

      {/* Clear All Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={clearAllConfirm}
        title="Clear All Verification Records?"
        message={`This will permanently remove all ${history.length} verification records from this session. Are you sure?`}
        confirmText="Clear All Records"
        cancelText="Cancel"
        isDanger={true}
        onConfirm={() => {
          onClearHistory();
          setClearAllConfirm(false);
        }}
        onCancel={() => setClearAllConfirm(false)}
      />
    </div>
  );
}
