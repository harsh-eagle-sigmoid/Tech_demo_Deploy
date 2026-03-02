import { useEffect, useState } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { fetchDrift, fetchResultDrift, executeSql } from './api';


export default function DriftPanel({ agentId, isActive = true }) {
  const [driftMode, setDriftMode] = useState('semantic'); // 'semantic' | 'result'

  // Semantic drift state
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState('');
  const [error, setError] = useState(null);
  const [selectedQuery, setSelectedQuery] = useState(null);

  // Result drift state
  const [resultData, setResultData] = useState(null);
  const [resultError, setResultError] = useState(null);
  const [selectedResultQuery, setSelectedResultQuery] = useState(null);

  // Use passed agentId if available, otherwise manual filter
  const activeFilter = agentId || filter;

  // Execution State
  const [execResult, setExecResult] = useState(null);
  const [execLoading, setExecLoading] = useState(false);

  // Load semantic drift
  const load = () => {
    if (!isActive) return;
    fetchDrift(activeFilter || undefined)
      .then(setData)
      .catch(e => setError(e.message));
  };

  // Load result drift
  const loadResultDrift = () => {
    if (!isActive) return;
    fetchResultDrift(activeFilter || undefined)
      .then(setResultData)
      .catch(e => setResultError(e.message));
  };

  useEffect(() => {
    load();
    loadResultDrift();
    const interval = setInterval(() => { load(); loadResultDrift(); }, 3000);
    return () => clearInterval(interval);
  }, [activeFilter, isActive]);

  // Auto-load output when semantic query selected
  useEffect(() => {
    if (!selectedQuery?.sql || !selectedQuery?.agent_type) {
      setExecResult(null);
      return;
    }
    if (selectedQuery.sql.includes("Not Available")) {
      setExecResult({ status: 'error', error: 'No SQL recorded.' });
      return;
    }
    setExecLoading(true);
    executeSql(selectedQuery.sql, selectedQuery.agent_type)
      .then(res => setExecResult(res))
      .catch(err => setExecResult({ status: 'error', error: err.message }))
      .finally(() => setExecLoading(false));
  }, [selectedQuery]);

  // ── Toggle buttons (always visible at top) ───────────────────────────────
  const toggleBar = (
    <div style={{ display: 'flex', gap: 0, alignItems: 'center', marginBottom: 20, background: '#131c2e', borderRadius: 8, padding: 4, width: 'fit-content', border: '1px solid #2a3548' }}>
      {[
        { key: 'semantic', label: 'Semantic Drift' },
        { key: 'result',   label: 'Result Drift' },
      ].map(({ key, label }) => (
        <button
          key={key}
          onClick={() => setDriftMode(key)}
          style={{
            padding: '7px 22px',
            border: 'none',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: '0.92rem',
            fontWeight: 600,
            transition: 'all 0.2s',
            background: driftMode === key ? '#4c9eff' : 'transparent',
            color: driftMode === key ? '#fff' : '#7a8fa3',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );

  // ── Semantic Drift View ──────────────────────────────────────────────────
  if (driftMode === 'semantic') {
    if (error) return <><div>{toggleBar}</div><p className="error-msg">{error}</p></>;
    if (!data) return <><div>{toggleBar}</div><p className="loading">Loading drift data...</p></>;

    const { distribution, total_anomalies, high_drift_samples } = data;
    const pieData = Object.entries(distribution).map(([name, d]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value: d.count, key: name,
    }));

    return (
      <>
        {toggleBar}

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

  // ── Result Drift View ────────────────────────────────────────────────────
  if (resultError) return <><div>{toggleBar}</div><p className="error-msg">{resultError}</p></>;
  if (!resultData) return <><div>{toggleBar}</div><p className="loading">Loading result drift data...</p></>;

  const { distribution: rd, total_anomalies: rAnomalies, high_drift_samples: rSamples, trend: rTrend, column_avg_psi } = resultData;

  const rdPieData = Object.entries(rd).map(([name, d]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: d.count, key: name,
  }));

  const PSI_COLOR = (psi) => psi >= 0.20 ? '#ff6b6b' : psi >= 0.10 ? '#f7b731' : '#3ecf8e';

  return (
    <>
      {toggleBar}

      {!agentId && (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 18, flexWrap: 'wrap' }}>
          {['', 'spend', 'demand'].map(v => (
            <button key={v} className={`tab-btn ${filter === v ? 'active' : ''}`} onClick={() => setFilter(v)}>
              {v || 'All'}
            </button>
          ))}
        </div>
      )}


      {/* KPI cards */}
      <div className="cards-row">
        <div className="card"><div className="label">Total Evaluated</div><div className="value blue">{rdPieData.reduce((s, d) => s + d.value, 0)}</div></div>
        <div className="card"><div className="label">PSI Anomalies</div><div className="value red">{rAnomalies}</div></div>
        <div className="card"><div className="label">Normal</div><div className="value green">{rd.normal?.count || 0}</div></div>
        <div className="card"><div className="label">Medium PSI</div><div className="value orange">{rd.medium?.count || 0}</div></div>
        <div className="card"><div className="label">High PSI</div><div className="value red">{rd.high?.count || 0}</div></div>
      </div>

      {/* Distribution + Column PSI */}
      <div className="panels-row">
        <div className="panel">
          <h3>PSI Distribution</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={rdPieData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
              <defs>
                <linearGradient id="rdGradNormal" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#3ecf8e" /><stop offset="100%" stopColor="#2ea043" />
                </linearGradient>
                <linearGradient id="rdGradMedium" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#4c9eff" /><stop offset="100%" stopColor="#8c52ff" />
                </linearGradient>
                <linearGradient id="rdGradHigh" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#ec4899" /><stop offset="100%" stopColor="#d946ef" />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" horizontal={false} />
              <XAxis type="number" stroke="#5a7a99" fontSize={12} />
              <YAxis dataKey="name" type="category" stroke="#5a7a99" fontSize={12} width={60} />
              <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ background: '#1e2736', border: '1px solid #2a3548', borderRadius: 6, color: '#c8d6e5' }} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {rdPieData.map((entry) => (
                  <Cell key={entry.key} fill={
                    entry.key === 'normal' ? 'url(#rdGradNormal)'
                      : entry.key === 'medium' ? 'url(#rdGradMedium)'
                        : 'url(#rdGradHigh)'
                  } />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel">
          <h3>Avg PSI by Classification</h3>
          <table className="data-table">
            <thead><tr><th>Level</th><th>Count</th><th>Avg PSI</th></tr></thead>
            <tbody>
              {Object.entries(rd).map(([lvl, d]) => (
                <tr key={lvl}>
                  <td><span className={`badge ${lvl}`}>{lvl}</span></td>
                  <td>{d.count}</td>
                  <td style={{ color: PSI_COLOR(d.avg_psi), fontWeight: 600 }}>{d.avg_psi}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Column-level PSI averages */}
      {column_avg_psi && column_avg_psi.length > 0 && (
        <div className="panel" style={{ marginBottom: '24px' }}>
          <h3>Column-Level Avg PSI (Top Drifting Columns)</h3>
          <div style={{ maxHeight: '260px', overflowY: 'auto' }}>
            <table className="data-table">
              <thead><tr><th>Column</th><th>Avg PSI</th><th>Status</th></tr></thead>
              <tbody>
                {column_avg_psi.map((c, i) => (
                  <tr key={i}>
                    <td className="mono" style={{ color: '#c8d6e5' }}>{c.column}</td>
                    <td style={{ color: PSI_COLOR(c.avg_psi), fontWeight: 600 }}>{c.avg_psi}</td>
                    <td>
                      <span className={`badge ${c.avg_psi >= 0.20 ? 'high' : c.avg_psi >= 0.10 ? 'medium' : 'normal'}`}>
                        {c.avg_psi >= 0.20 ? 'High' : c.avg_psi >= 0.10 ? 'Medium' : 'Normal'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* PSI Trend */}
      <div className="panel" style={{ marginBottom: '24px' }}>
        <h3>PSI Trend (Daily Average)</h3>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={rTrend} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" />
            <XAxis dataKey="date" stroke="#5a7a99" fontSize={12} />
            <YAxis stroke="#5a7a99" fontSize={12} domain={[0, 'auto']} />
            <Tooltip contentStyle={{ background: '#1e2736', border: '1px solid #2a3548', color: '#c8d6e5' }}
              formatter={(v) => [v, 'Avg PSI']} />
            <Line type="monotone" dataKey="avg_psi" stroke="#f7b731" strokeWidth={3} dot={{ fill: '#f7b731', r: 4 }} activeDot={{ r: 6 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* High-PSI Anomalies table */}
      <div className="panel" style={{ marginBottom: '24px' }}>
        <h3>High-PSI Anomalies (Select to view PSI details)</h3>
        <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid #334155', borderRadius: '6px' }}>
          <table className="data-table" style={{ margin: 0 }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 5 }}>
              <tr><th>Query</th><th>Query ID</th><th>Overall PSI</th><th>Columns</th><th>Level</th></tr>
            </thead>
            <tbody>
              {rSamples.map((s, i) => (
                <tr key={i} onClick={() => setSelectedResultQuery(selectedResultQuery?.query_id === s.query_id ? null : s)}
                  style={{ cursor: 'pointer', backgroundColor: selectedResultQuery?.query_id === s.query_id ? 'rgba(247,183,49,0.1)' : 'transparent', transition: 'background 0.2s' }}>
                  <td style={{ color: '#e2e8f0', maxWidth: '300px' }}>{s.query_text}</td>
                  <td className="mono" style={{ fontSize: '0.85em', color: '#94a3b8' }}>{s.query_id}</td>
                  <td style={{ color: '#ff6b6b', fontWeight: 600 }}>{s.overall_psi}</td>
                  <td style={{ color: '#94a3b8' }}>{s.columns_analyzed}</td>
                  <td><span className="badge high">{s.classification}</span></td>
                </tr>
              ))}
              {rSamples.length === 0 && (
                <tr><td colSpan={5} style={{ color: '#5a7a99', fontStyle: 'italic', textAlign: 'center', padding: '24px' }}>No high-PSI anomalies detected.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* PSI Detail Panel */}
      {selectedResultQuery && (
        <div className="panel" style={{ borderTop: '4px solid #f7b731', animation: 'fadeIn 0.3s' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3>PSI Details — {selectedResultQuery.query_id}</h3>
            <button onClick={() => setSelectedResultQuery(null)} style={{ background: 'none', border: 'none', color: '#7a8fa3', cursor: 'pointer' }}>✕ Close</button>
          </div>

          <div style={{ marginBottom: '16px', padding: '14px', background: '#0f1420', borderRadius: 8, color: '#e2e8f0', lineHeight: 1.6 }}>
            {selectedResultQuery.query_text}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
            <div>
              <div className="label" style={{ marginBottom: 12 }}>PSI Scores by Column</div>
              <table className="data-table">
                <thead><tr><th>Column</th><th>PSI Score</th><th>Status</th></tr></thead>
                <tbody>
                  {Object.entries(selectedResultQuery.psi_scores).map(([col, psi]) => (
                    <tr key={col}>
                      <td className="mono" style={{ color: '#c8d6e5' }}>{col}</td>
                      <td style={{ color: PSI_COLOR(psi), fontWeight: 600 }}>{psi}</td>
                      <td>
                        <span className={`badge ${psi >= 0.20 ? 'high' : psi >= 0.10 ? 'medium' : 'normal'}`}>
                          {psi >= 0.20 ? 'High' : psi >= 0.10 ? 'Medium' : 'Normal'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <div className="label" style={{ marginBottom: 12 }}>Summary</div>
              <div style={{ background: '#0f1420', borderRadius: 8, padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                  <span style={{ color: '#7a8fa3' }}>Overall PSI</span>
                  <span style={{ color: PSI_COLOR(selectedResultQuery.overall_psi), fontWeight: 700, fontSize: '1.2rem' }}>{selectedResultQuery.overall_psi}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                  <span style={{ color: '#7a8fa3' }}>Columns Analyzed</span>
                  <span style={{ color: '#c8d6e5' }}>{selectedResultQuery.columns_analyzed}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#7a8fa3' }}>Classification</span>
                  <span className={`badge high`}>{selectedResultQuery.classification}</span>
                </div>
              </div>
              <div className="label" style={{ marginBottom: 12, marginTop: 20 }}>Generated SQL</div>
              <pre style={{ padding: '14px', background: '#0f1420', borderRadius: '8px', color: '#8ecae6', overflowX: 'auto', fontFamily: 'Consolas, monospace', fontSize: '0.85rem', whiteSpace: 'pre-wrap', lineHeight: '1.6', maxHeight: 200, overflowY: 'auto' }}>
                {selectedResultQuery.sql}
              </pre>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
