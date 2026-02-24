import React, { useState, useEffect } from 'react';
import './DataQualityBadge.css';

/**
 * DataQualityBadge Component
 *
 * Compact badge showing data quality status for an agent.
 * Used in agent lists and summaries.
 */
const DataQualityBadge = ({ agentId, compact = false }) => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (agentId) {
      fetchSummary();
    }
  }, [agentId]);

  const fetchSummary = async () => {
    try {
      const response = await fetch(`/api/v1/agents/${agentId}/data-quality`);

      if (!response.ok) {
        setSummary({ total_issues: 0, critical: 0, warnings: 0, info: 0 });
        return;
      }

      const data = await response.json();
      setSummary({
        total_issues: data.total_issues,
        critical: data.critical,
        warnings: data.warnings,
        info: data.info
      });
    } catch (err) {
      console.error('Error fetching data quality summary:', err);
      setSummary({ total_issues: 0, critical: 0, warnings: 0, info: 0 });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return compact ? (
      <span className="dq-badge loading-compact">...</span>
    ) : (
      <div className="dq-badge-loading">Loading...</div>
    );
  }

  if (!summary) {
    return null;
  }

  // Determine overall status
  const getStatus = () => {
    if (summary.critical > 0) return 'critical';
    if (summary.warnings > 0) return 'warning';
    if (summary.info > 0) return 'info';
    return 'healthy';
  };

  const status = getStatus();

  const getStatusIcon = () => {
    switch (status) {
      case 'critical':
        return '🔴';
      case 'warning':
        return '⚠️';
      case 'info':
        return 'ℹ️';
      case 'healthy':
        return '✅';
      default:
        return '●';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'critical':
        return `${summary.critical} Critical`;
      case 'warning':
        return `${summary.warnings} Warning${summary.warnings !== 1 ? 's' : ''}`;
      case 'info':
        return `${summary.info} Info`;
      case 'healthy':
        return 'Healthy';
      default:
        return 'Unknown';
    }
  };

  if (compact) {
    return (
      <span className={`dq-badge compact ${status}`} title={getStatusText()}>
        {getStatusIcon()}
      </span>
    );
  }

  return (
    <div className={`dq-badge ${status}`}>
      <span className="badge-icon">{getStatusIcon()}</span>
      <span className="badge-text">{getStatusText()}</span>
      {summary.total_issues > 0 && (
        <span className="badge-count">{summary.total_issues}</span>
      )}
    </div>
  );
};

export default DataQualityBadge;
