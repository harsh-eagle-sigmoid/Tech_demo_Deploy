import { useState, useEffect } from 'react';
import { fetchSchemaStatus, fetchSchemaChanges, scanSchemaChanges } from './api';
import { Database, RefreshCw, Clock, GitBranch, AlertCircle } from 'lucide-react';

export default function SchemaPanel({ agentId, isActive }) {
  const [status, setStatus] = useState(null);
  const [changes, setChanges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);

  const loadData = async () => {
    if (!agentId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const [statusData, changesData] = await Promise.all([
        fetchSchemaStatus(agentId),
        fetchSchemaChanges(agentId, 20)
      ]);
      setStatus(statusData);
      setChanges(changesData?.changes || []);
      setError(null);
    } catch (err) {
      console.error('Schema panel error:', err);
      setError(err?.response?.data?.detail || err.message || 'Failed to load schema data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isActive) {
      loadData();
      const interval = setInterval(loadData, 30000); // Refresh every 30s
      return () => clearInterval(interval);
    }
  }, [agentId, isActive]);

  const handleScanNow = async () => {
    if (!agentId) return;
    setScanning(true);
    try {
      await scanSchemaChanges(agentId);
      alert('Schema scan started. This may take 1-2 minutes. New queries will be generated for any detected changes.');
      setTimeout(loadData, 3000); // Reload after 3s
    } catch (err) {
      alert(err?.response?.data?.detail || 'Failed to start schema scan');
    } finally {
      setScanning(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (!agentId) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
        <Database size={32} style={{ opacity: 0.3 }} />
        <p style={{ marginTop: 10 }}>Please select an agent to view schema monitoring</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
        <RefreshCw size={24} className="spin" />
        <p style={{ marginTop: 10 }}>Loading schema data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: '#ff6b6b' }}>
        <AlertCircle size={24} />
        <p style={{ marginTop: 10 }}>{error}</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px 30px' }}>
      {/* Header with Scan Button */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 30
      }}>
        <div>
          <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: 6 }}>
            Schema Monitoring
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Track database schema changes and incremental ground truth generation
          </p>
        </div>
        <button
          onClick={handleScanNow}
          disabled={scanning}
          style={{
            background: scanning ? 'rgba(76, 158, 255, 0.1)' : 'linear-gradient(135deg, #4c9eff 0%, #3ecf8e 100%)',
            color: scanning ? 'var(--text-muted)' : '#fff',
            border: 'none',
            padding: '12px 24px',
            borderRadius: 8,
            cursor: scanning ? 'not-allowed' : 'pointer',
            fontSize: '0.95rem',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            transition: 'all 0.2s'
          }}
        >
          <RefreshCw size={18} className={scanning ? 'spin' : ''} />
          {scanning ? 'Scanning...' : 'Scan Schema Now'}
        </button>
      </div>

      {/* Status Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: 20,
        marginBottom: 30
      }}>
        {/* Schema Version */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <GitBranch size={20} style={{ color: '#4c9eff' }} />
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 500 }}>
              Schema Version
            </span>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            v{status?.schema_version || 1}
          </div>
        </div>

        {/* Last Scan */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <Clock size={20} style={{ color: '#3ecf8e' }} />
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 500 }}>
              Last Scan
            </span>
          </div>
          <div style={{ fontSize: '1.3rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            {formatDate(status?.last_schema_scan_at)}
          </div>
        </div>

        {/* Total Changes */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <Database size={20} style={{ color: '#ffc107' }} />
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 500 }}>
              Total Changes
            </span>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {status?.schema_change_count || 0}
          </div>
        </div>
      </div>

      {/* Changes History */}
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{
          color: 'var(--text-primary)',
          fontSize: '1.1rem',
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}>
          <Database size={20} />
          Recent Schema Changes
        </h3>

        {changes.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '40px 20px',
            color: 'var(--text-muted)'
          }}>
            <Database size={32} style={{ opacity: 0.3, marginBottom: 10 }} />
            <p>No schema changes detected yet</p>
            <p style={{ fontSize: '0.85rem', marginTop: 5 }}>
              Click "Scan Schema Now" to check for changes
            </p>
          </div>
        ) : (
          <div style={{ maxHeight: 500, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <th style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 500 }}>
                    Type
                  </th>
                  <th style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 500 }}>
                    Schema
                  </th>
                  <th style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 500 }}>
                    Table
                  </th>
                  <th style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 500 }}>
                    Column
                  </th>
                  <th style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 500 }}>
                    Detected
                  </th>
                  <th style={{ textAlign: 'center', padding: '10px 12px', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 500 }}>
                    GT Generated
                  </th>
                </tr>
              </thead>
              <tbody>
                {changes.map((change, idx) => (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: '1px solid var(--border-color)',
                      transition: 'background 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(76, 158, 255, 0.05)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '12px', fontSize: '0.9rem' }}>
                      <span style={{
                        padding: '4px 8px',
                        borderRadius: 4,
                        fontSize: '0.75rem',
                        fontWeight: 500,
                        background: change.change_type === 'table_added' ? 'rgba(62, 207, 142, 0.15)' : 'rgba(76, 158, 255, 0.15)',
                        color: change.change_type === 'table_added' ? '#3ecf8e' : '#4c9eff'
                      }}>
                        {change.change_type === 'table_added' ? '+ Table' : '+ Column'}
                      </span>
                    </td>
                    <td style={{ padding: '12px', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                      {change.schema_name || 'public'}
                    </td>
                    <td style={{ padding: '12px', color: 'var(--text-primary)', fontSize: '0.9rem', fontWeight: 500 }}>
                      {change.table_name}
                    </td>
                    <td style={{ padding: '12px', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                      {change.column_name || '-'}
                    </td>
                    <td style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      {formatDate(change.detected_at)}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      {change.gt_generated ? (
                        <span style={{ color: '#3ecf8e', fontSize: '1.1rem' }}>✓</span>
                      ) : (
                        <span style={{ color: '#ff6b6b', fontSize: '1.1rem' }}>✗</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Info Box */}
      <div style={{
        marginTop: 20,
        padding: 16,
        background: 'rgba(76, 158, 255, 0.08)',
        border: '1px solid rgba(76, 158, 255, 0.2)',
        borderRadius: 8,
        fontSize: '0.85rem',
        color: 'var(--text-secondary)'
      }}>
        <strong style={{ color: '#4c9eff' }}>ℹ Automatic Monitoring:</strong> Schemas are automatically scanned every 10 hours.
        New tables/columns generate incremental ground truth queries (10 per table, max 100) without regenerating all 500 queries.
      </div>
    </div>
  );
}
