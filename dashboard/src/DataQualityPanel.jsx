import React, { useState, useEffect } from 'react';
import { fetchDataQuality, revalidateDataQuality } from './api';
import './DataQualityPanel.css';

/**
 * DataQualityPanel Component
 *
 * Displays data quality validation issues for a specific agent.
 * Shows severity breakdown, issue details, and allows filtering.
 */
const DataQualityPanel = ({ agentId, agentName }) => {
  const [issues, setIssues] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all'); // 'all', 'critical', 'warning', 'info'
  const [expandedIssue, setExpandedIssue] = useState(null);

  useEffect(() => {
    if (agentId) {
      fetchDataQualityIssues();
    }
  }, [agentId]);

  const fetchDataQualityIssues = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchDataQuality(agentId);
      setIssues(data);
    } catch (err) {
      console.error('Error fetching data quality issues:', err);
      setError(err.message || 'Failed to fetch data quality issues');
    } finally {
      setLoading(false);
    }
  };

  const handleRevalidate = async () => {
    try {
      setLoading(true);
      await revalidateDataQuality(agentId);

      // Wait a bit for validation to complete
      setTimeout(() => {
        fetchDataQualityIssues();
      }, 3000);
    } catch (err) {
      console.error('Error triggering revalidation:', err);
      setError(err.message || 'Revalidation failed');
      setLoading(false);
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical':
        return '#dc3545'; // Red
      case 'warning':
        return '#ffc107'; // Yellow
      case 'info':
        return '#17a2b8'; // Blue
      default:
        return '#6c757d'; // Gray
    }
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical':
        return '🔴';
      case 'warning':
        return '⚠️';
      case 'info':
        return 'ℹ️';
      default:
        return '●';
    }
  };

  const formatIssueType = (type) => {
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const getFilteredIssues = () => {
    if (!issues || !issues.issues) return [];

    if (filter === 'all') {
      return issues.issues;
    }

    return issues.issues.filter(issue => issue.severity === filter);
  };

  if (loading && !issues) {
    return (
      <div className="data-quality-panel">
        <div className="loading">
          <div className="spinner"></div>
          <p>Loading data quality issues...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="data-quality-panel">
        <div className="error">
          <p>❌ Error: {error}</p>
          <button onClick={fetchDataQualityIssues}>Retry</button>
        </div>
      </div>
    );
  }

  if (!issues) {
    return null;
  }

  const filteredIssues = getFilteredIssues();

  return (
    <div className="data-quality-panel">
      {/* Header */}
      <div className="panel-header">
        <div className="header-left">
          <h2>Data Quality Issues</h2>
          {agentName && <span className="agent-name">{agentName}</span>}
        </div>
        <button
          className="btn-revalidate"
          onClick={handleRevalidate}
          disabled={loading}
        >
          {loading ? '⟳ Validating...' : '⟳ Revalidate'}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="summary-cards">
        <div
          className={`summary-card total ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          <div className="card-value">{issues.total_issues}</div>
          <div className="card-label">Total Issues</div>
        </div>

        <div
          className={`summary-card critical ${filter === 'critical' ? 'active' : ''}`}
          onClick={() => setFilter('critical')}
        >
          <div className="card-value">{issues.critical}</div>
          <div className="card-label">🔴 Critical</div>
        </div>

        <div
          className={`summary-card warning ${filter === 'warning' ? 'active' : ''}`}
          onClick={() => setFilter('warning')}
        >
          <div className="card-value">{issues.warnings}</div>
          <div className="card-label">⚠️ Warnings</div>
        </div>

        <div
          className={`summary-card info ${filter === 'info' ? 'active' : ''}`}
          onClick={() => setFilter('info')}
        >
          <div className="card-value">{issues.info}</div>
          <div className="card-label">ℹ️ Info</div>
        </div>
      </div>

      {/* Issues List */}
      {filteredIssues.length === 0 ? (
        <div className="no-issues">
          <div className="success-icon">✅</div>
          <h3>No {filter !== 'all' ? filter : ''} issues found!</h3>
          <p>Database passed all validation checks.</p>
        </div>
      ) : (
        <div className="issues-list">
          {filteredIssues.map((issue) => (
            <div
              key={issue.issue_id}
              className={`issue-card ${issue.severity}`}
              onClick={() => setExpandedIssue(expandedIssue === issue.issue_id ? null : issue.issue_id)}
            >
              <div className="issue-header">
                <div className="issue-left">
                  <span className="severity-icon">
                    {getSeverityIcon(issue.severity)}
                  </span>
                  <div className="issue-info">
                    <div className="issue-title">
                      {formatIssueType(issue.issue_type)}
                    </div>
                    <div className="issue-location">
                      {issue.schema_name}.{issue.table_name}
                      {issue.column_name && ` → ${issue.column_name}`}
                    </div>
                  </div>
                </div>
                <div className="issue-right">
                  <span
                    className="severity-badge"
                    style={{ backgroundColor: getSeverityColor(issue.severity) }}
                  >
                    {issue.severity.toUpperCase()}
                  </span>
                  <span className="expand-icon">
                    {expandedIssue === issue.issue_id ? '▼' : '▶'}
                  </span>
                </div>
              </div>

              <div className="issue-message">
                {issue.message}
              </div>

              {/* Expanded Details */}
              {expandedIssue === issue.issue_id && (
                <div className="issue-details">
                  {issue.affected_rows !== null && (
                    <div className="detail-row">
                      <span className="detail-label">Affected Rows:</span>
                      <span className="detail-value">
                        {issue.affected_rows.toLocaleString()}
                        {issue.total_rows && ` / ${issue.total_rows.toLocaleString()}`}
                        {issue.percentage && ` (${issue.percentage}%)`}
                      </span>
                    </div>
                  )}

                  {issue.details && Object.keys(issue.details).length > 0 && (
                    <div className="detail-row">
                      <span className="detail-label">Details:</span>
                      <pre className="detail-value">
                        {JSON.stringify(issue.details, null, 2)}
                      </pre>
                    </div>
                  )}

                  <div className="detail-row">
                    <span className="detail-label">Discovered:</span>
                    <span className="detail-value">
                      {new Date(issue.discovered_at).toLocaleString()}
                    </span>
                  </div>

                  <div className="detail-row">
                    <span className="detail-label">Status:</span>
                    <span className={`status-badge ${issue.status}`}>
                      {issue.status}
                    </span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DataQualityPanel;
