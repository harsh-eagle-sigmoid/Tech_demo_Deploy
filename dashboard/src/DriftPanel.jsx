import { useEffect, useState } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { fetchDrift, executeSql } from './api';

const COLORS = { normal: '#3ecf8e', medium: '#f7b731', high: '#ff6b6b' };

export default function DriftPanel({ agentId, isActive = true }) {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState('');
  const [error, setError] = useState(null);
  const [selectedQuery, setSelectedQuery] = useState(null);

  // Use passed agentId if available, otherwise manual filter
  const activeFilter = agentId || filter;

  // Execution State
  const [execResult, setExecResult] = useState(null);
  const [execLoading, setExecLoading] = useState(false);

  const load = () => {
    if (!isActive) return;
    fetchDrift(activeFilter || undefined)
      .then(setData)
      .catch(e => setError(e.message));
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [activeFilter, isActive]);

  // Auto-load output when query selected
  useEffect(() => {
    if (!selectedQuery?.sql || !selectedQuery?.agent_type) {
      setExecResult(null);
      return;
    }

    // If no SQL, skip
    if (selectedQuery.sql.includes("Not Available")) {
      setExecResult({ status: 'error', error: 'No SQL recorded.' });
      return;
    }

    setExecLoading(true);
    // Simulating "fetching static output" by re-executing
    executeSql(selectedQuery.sql, selectedQuery.agent_type)
      .then(res => setExecResult(res))
      .catch(err => setExecResult({ status: 'error', error: err.message }))
      .finally(() => setExecLoading(false));

  }, [selectedQuery]);

  if (error) return <p className="error-msg">{error}</p>;
  if (!data) return <p className="loading">Loading drift data...</p>;

  const { distribution, total_anomalies, high_drift_samples } = data;
  const pieData = Object.entries(distribution).map(([name, d]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: d.count, key: name,
  }));

  return (
    <>
      {!agentId && (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 18, flexWrap: 'wrap' }}>
          {['', 'spend', 'demand'].map(v => (
            <button key={v} className={`tab-btn ${filter === v ? 'active' : ''}`} onClick={() => setFilter(v)}>
              {v || 'All'}
            </button>
          ))}
        </div>
      )}

      <div className="cards-row">
        <div className="card"><div className="label">Total Monitored</div><div className="value blue">{pieData.reduce((s, d) => s + d.value, 0)}</div></div>
        <div className="card"><div className="label">Anomalies</div><div className="value red">{total_anomalies}</div></div>
        <div className="card"><div className="label">Normal</div><div className="value green">{distribution.normal?.count || 0}</div></div>
        <div className="card"><div className="label">Medium Drift</div><div className="value orange">{distribution.medium?.count || 0}</div></div>
        <div className="card"><div className="label">High Drift</div><div className="value red">{distribution.high?.count || 0}</div></div>
      </div>

      <div className="panels-row">
        <div className="panel">
          <h3>Drift Distribution</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={pieData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
              <defs>
                <linearGradient id="gradNormal" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#3ecf8e" />
                  <stop offset="100%" stopColor="#2ea043" />
                </linearGradient>
                <linearGradient id="gradMedium" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#4c9eff" />
                  <stop offset="100%" stopColor="#8c52ff" />
                </linearGradient>
                <linearGradient id="gradHigh" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#ec4899" />
                  <stop offset="100%" stopColor="#d946ef" />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" horizontal={false} />
              <XAxis type="number" stroke="#5a7a99" fontSize={12} />
              <YAxis dataKey="name" type="category" stroke="#5a7a99" fontSize={12} width={60} />
              <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ background: '#1e2736', border: '1px solid #2a3548', borderRadius: 6, color: '#c8d6e5' }} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {pieData.map((entry) => {
                  const fillUrl = entry.key === 'normal' ? 'url(#gradNormal)'
                    : entry.key === 'medium' ? 'url(#gradMedium)'
                      : 'url(#gradHigh)';
                  return <Cell key={entry.key} fill={fillUrl} />;
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <h3>Avg Drift Score by Level</h3>
          <table className="data-table">
            <thead><tr><th>Level</th><th>Count</th><th>Avg Score</th></tr></thead>
            <tbody>
              {Object.entries(distribution).map(([lvl, d]) => (
                <tr key={lvl}>
                  <td><span className={`badge ${lvl}`}>{lvl}</span></td>
                  <td>{d.count}</td>
                  <td>{d.avg_drift_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* NEW TREND PANEL */}
      <div className="panel" style={{ marginBottom: '24px' }}>
        <h3>Drift Trend (Daily Average)</h3>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data.trend} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" />
            <XAxis dataKey="date" stroke="#5a7a99" fontSize={12} />
            <YAxis stroke="#5a7a99" fontSize={12} domain={[0, 1]} />
            <Tooltip contentStyle={{ background: '#1e2736', border: '1px solid #2a3548', color: '#c8d6e5' }} />
            <Line type="monotone" dataKey="avg_score" stroke="#4c9eff" strokeWidth={3} dot={{ fill: '#4c9eff', r: 4 }} activeDot={{ r: 6 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="panel" style={{ marginBottom: '24px' }}>
        <h3>Top High-Drift Queries (Select to view details)</h3>
        <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid #334155', borderRadius: '6px' }}>
          <table className="data-table" style={{ margin: 0 }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 5 }}>
              <tr><th>Query</th><th>Query ID</th><th>Drift Score</th><th>Level</th></tr>
            </thead>
            <tbody>
              {high_drift_samples.map((s, i) => (
                <tr key={i} onClick={() => setSelectedQuery(s)}
                  style={{ cursor: 'pointer', backgroundColor: selectedQuery?.query_id === s.query_id ? 'rgba(76, 158, 255, 0.1)' : 'transparent', transition: 'background 0.2s' }}>
                  <td style={{ color: '#e2e8f0', maxWidth: '300px' }}>{s.query_text}</td>
                  <td className="mono" style={{ fontSize: '0.85em', color: '#94a3b8' }}>{s.query_id}</td>
                  <td style={{ color: '#ff6b6b', fontWeight: 600 }}>{s.drift_score}</td>
                  <td><span className="badge high">{s.classification}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedQuery && (
        <div className="panel" style={{ borderTop: '4px solid #4c9eff', animation: 'fadeIn 0.3s' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3>Query Details</h3>
            <button onClick={() => setSelectedQuery(null)} style={{ background: 'none', border: 'none', color: '#7a8fa3', cursor: 'pointer' }}>✕ Close</button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: '40px' }}>
            <div>
              <div className="label" style={{ marginBottom: '12px' }}>Natural Language Query</div>
              <div style={{ padding: '16px', background: '#0f1420', borderRadius: '8px', color: '#fff', fontSize: '1.1rem', marginBottom: '24px', lineHeight: '1.5' }}>
                {selectedQuery.query_text}
              </div>
              <div className="label" style={{ marginBottom: '12px' }}>Generated SQL</div>
              <pre style={{ padding: '16px', background: '#0f1420', borderRadius: '8px', color: '#8ecae6', overflowX: 'auto', fontFamily: 'Consolas, monospace', fontSize: '0.9rem', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                {selectedQuery.sql}
              </pre>
            </div>

            <div>
              <div className="label" style={{ marginBottom: '12px' }}>Query Output</div>
              <div style={{ background: '#0f1420', padding: '20px', borderRadius: '8px', minHeight: '200px' }}>
                {execLoading ? (
                  <div style={{ color: '#5a7a99', fontStyle: 'italic', padding: '20px' }}>Loading output...</div>
                ) : !execResult ? (
                  <div style={{ color: '#7a8fa3' }}>No output data.</div>
                ) : execResult.status === 'error' ? (
                  <div style={{ color: '#ff6b6b', fontFamily: 'monospace' }}>{execResult.error}</div>
                ) : execResult.results.length === 0 ? (
                  <div style={{ color: '#7a8fa3', fontStyle: 'italic' }}>0 rows returned.</div>
                ) : (
                  <div style={{ overflowX: 'auto', maxHeight: '300px' }}>
                    <table className="data-table">
                      <thead>
                        <tr>{Object.keys(execResult.results[0]).map(k => <th key={k}>{k}</th>)}</tr>
                      </thead>
                      <tbody>
                        {execResult.results.map((row, idx) => (
                          <tr key={idx}>{Object.values(row).map((v, i) => <td key={i}>{String(v)}</td>)}</tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
